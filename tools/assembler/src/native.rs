//! Windows execution ownership. No child runs before assignment to our job.
use std::os::windows::{ffi::OsStrExt, io::AsRawHandle};
use std::{
    fs::{self, File, OpenOptions},
    io,
    path::{Path, PathBuf},
    time::{Duration, Instant},
};
use windows_sys::Win32::{
    Foundation::*,
    Security::SECURITY_ATTRIBUTES,
    Storage::FileSystem::MoveFileExW,
    System::{JobObjects::*, Threading::*},
};

pub fn wide(value: &std::ffi::OsStr) -> Vec<u16> {
    value.encode_wide().chain(Some(0)).collect()
}
fn quote(value: &str) -> String {
    let mut result = String::from("\"");
    let mut slashes = 0;
    for c in value.chars() {
        if c == '\\' {
            slashes += 1;
            continue;
        }
        if c == '"' {
            result.push_str(&"\\".repeat(slashes * 2 + 1));
        } else {
            result.push_str(&"\\".repeat(slashes));
        }
        slashes = 0;
        result.push(c);
    }
    result.push_str(&"\\".repeat(slashes * 2));
    result.push('"');
    result
}
struct Owned(HANDLE);
impl Drop for Owned {
    fn drop(&mut self) {
        if !self.0.is_null() && self.0 != INVALID_HANDLE_VALUE {
            unsafe {
                CloseHandle(self.0);
            }
        }
    }
}

pub struct Process {
    job: Owned,
    process: Owned,
    pub pid: u32,
    pub started: Instant,
    pub stdout: PathBuf,
    pub stderr: PathBuf,
}
impl Process {
    pub fn spawn(executable: &Path, args: &[String], cwd: &Path, logs: &Path) -> io::Result<Self> {
        Self::spawn_with_environment(executable, args, cwd, logs, None)
    }
    pub fn spawn_with_environment(
        executable: &Path,
        args: &[String],
        cwd: &Path,
        logs: &Path,
        environment: Option<&[(std::ffi::OsString, std::ffi::OsString)]>,
    ) -> io::Result<Self> {
        let mut environment_block = Vec::<u16>::new();
        if let Some(environment) = environment {
            let mut entries = environment.to_vec();
            entries.sort_by_key(|(key, _)| key.to_string_lossy().to_uppercase());
            for (key, value) in entries {
                let key_units: Vec<_> = key.encode_wide().collect();
                let value_units: Vec<_> = value.encode_wide().collect();
                if key_units.is_empty()
                    || key_units.contains(&0)
                    || key_units.contains(&(b'=' as u16))
                    || value_units.contains(&0)
                {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidInput,
                        "invalid environment entry",
                    ));
                }
                environment_block.extend(key_units);
                environment_block.push(b'=' as u16);
                environment_block.extend(value_units);
                environment_block.push(0);
            }
            environment_block.push(0);
            if environment_block.len() == 1 {
                environment_block.push(0);
            }
        }
        fs::create_dir_all(logs)?;
        let out_path = logs.join("stdout.log");
        let err_path = logs.join("stderr.log");
        let stdout = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&out_path)?;
        let stderr = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&err_path)?;
        let stdin = File::open("NUL")?;
        let handles = [
            stdin.as_raw_handle() as HANDLE,
            stdout.as_raw_handle() as HANDLE,
            stderr.as_raw_handle() as HANDLE,
        ];
        unsafe {
            for h in handles {
                if SetHandleInformation(h, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT) == 0 {
                    return Err(io::Error::last_os_error());
                }
            }
            let job = Owned(CreateJobObjectW(
                std::ptr::null::<SECURITY_ATTRIBUTES>(),
                std::ptr::null(),
            ));
            if job.0.is_null() {
                return Err(io::Error::last_os_error());
            }
            let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(
                job.0,
                JobObjectExtendedLimitInformation,
                &limits as *const _ as _,
                std::mem::size_of_val(&limits) as u32,
            ) == 0
            {
                return Err(io::Error::last_os_error());
            }
            let mut bytes = 0;
            InitializeProcThreadAttributeList(std::ptr::null_mut(), 1, 0, &mut bytes);
            let mut storage = vec![0usize; bytes.div_ceil(std::mem::size_of::<usize>())];
            let attributes = storage.as_mut_ptr() as LPPROC_THREAD_ATTRIBUTE_LIST;
            if InitializeProcThreadAttributeList(attributes, 1, 0, &mut bytes) == 0 {
                return Err(io::Error::last_os_error());
            }
            if UpdateProcThreadAttribute(
                attributes,
                0,
                PROC_THREAD_ATTRIBUTE_HANDLE_LIST as usize,
                handles.as_ptr() as _,
                std::mem::size_of_val(&handles),
                std::ptr::null_mut(),
                std::ptr::null(),
            ) == 0
            {
                let error = io::Error::last_os_error();
                DeleteProcThreadAttributeList(attributes);
                return Err(error);
            }
            let mut startup: STARTUPINFOEXW = std::mem::zeroed();
            startup.StartupInfo.cb = std::mem::size_of_val(&startup) as u32;
            startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
            startup.StartupInfo.hStdInput = handles[0];
            startup.StartupInfo.hStdOutput = handles[1];
            startup.StartupInfo.hStdError = handles[2];
            startup.lpAttributeList = attributes;
            let exe = wide(executable.as_os_str());
            let cwd = wide(cwd.as_os_str());
            let line = std::iter::once(executable.to_string_lossy().to_string())
                .chain(args.iter().cloned())
                .map(|s| quote(&s))
                .collect::<Vec<_>>()
                .join(" ");
            let mut command = wide(std::ffi::OsStr::new(&line));
            let mut info: PROCESS_INFORMATION = std::mem::zeroed();
            let started = Instant::now();
            let success = CreateProcessW(
                exe.as_ptr(),
                command.as_mut_ptr(),
                std::ptr::null(),
                std::ptr::null(),
                1,
                CREATE_SUSPENDED
                    | CREATE_NO_WINDOW
                    | EXTENDED_STARTUPINFO_PRESENT
                    | CREATE_UNICODE_ENVIRONMENT,
                if environment.is_some() {
                    environment_block.as_ptr() as _
                } else {
                    std::ptr::null()
                },
                cwd.as_ptr(),
                &startup.StartupInfo,
                &mut info,
            );
            let error = io::Error::last_os_error();
            DeleteProcThreadAttributeList(attributes);
            if success == 0 {
                return Err(error);
            }
            let process = Owned(info.hProcess);
            let thread = Owned(info.hThread);
            if AssignProcessToJobObject(job.0, process.0) == 0 {
                let error = io::Error::last_os_error();
                TerminateProcess(process.0, 1);
                WaitForSingleObject(process.0, 5000);
                return Err(error);
            }
            if ResumeThread(thread.0) == u32::MAX {
                return Err(io::Error::last_os_error());
            }
            Ok(Self {
                job,
                process,
                pid: info.dwProcessId,
                started,
                stdout: out_path,
                stderr: err_path,
            })
        }
    }
    pub fn active(&self) -> io::Result<u32> {
        let mut info: JOBOBJECT_BASIC_ACCOUNTING_INFORMATION = unsafe { std::mem::zeroed() };
        if unsafe {
            QueryInformationJobObject(
                self.job.0,
                JobObjectBasicAccountingInformation,
                &mut info as *mut _ as _,
                std::mem::size_of_val(&info) as u32,
                std::ptr::null_mut(),
            )
        } == 0
        {
            return Err(io::Error::last_os_error());
        }
        Ok(info.ActiveProcesses)
    }
    pub fn process_ids(&self) -> io::Result<Vec<usize>> {
        // The supervisor only needs a bounded diagnostic sample; active() remains authoritative.
        let mut storage = vec![0usize; 258];
        if unsafe {
            QueryInformationJobObject(
                self.job.0,
                JobObjectBasicProcessIdList,
                storage.as_mut_ptr() as _,
                (storage.len() * std::mem::size_of::<usize>()) as u32,
                std::ptr::null_mut(),
            )
        } == 0
        {
            return Err(io::Error::last_os_error());
        }
        let list = unsafe { &*(storage.as_ptr() as *const JOBOBJECT_BASIC_PROCESS_ID_LIST) };
        let offset = std::mem::size_of::<u32>() * 2 / std::mem::size_of::<usize>();
        Ok(storage[offset..offset + list.NumberOfProcessIdsInList as usize].to_vec())
    }
    pub fn exit_code(&self) -> io::Result<u32> {
        let mut code = 0;
        if unsafe { GetExitCodeProcess(self.process.0, &mut code) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(code)
    }
    pub fn terminate(&self) -> io::Result<()> {
        if unsafe { TerminateJobObject(self.job.0, 1) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
    pub fn settle(&self, budget: Duration) -> io::Result<bool> {
        let start = Instant::now();
        loop {
            if self.active()? == 0 {
                return Ok(true);
            }
            if start.elapsed() >= budget {
                return Ok(false);
            }
            std::thread::sleep(Duration::from_millis(10));
        }
    }
    pub fn overflow(&self, limit: u64) -> io::Result<bool> {
        Ok(fs::metadata(&self.stdout)?.len() > limit || fs::metadata(&self.stderr)?.len() > limit)
    }

    /// Supervise a noninteractive tool. Guest verification adds its own marker/QMP protocol.
    /// Files can briefly exceed the cap between polls; retained captures are truncated only
    /// after every owned process has settled. This is not a filesystem quota.
    pub fn supervise(
        &self,
        deadline: Duration,
        cancelled: &std::sync::atomic::AtomicBool,
        limit: u64,
    ) -> io::Result<Completion> {
        use std::sync::atomic::Ordering;
        let reason = loop {
            if cancelled.load(Ordering::SeqCst) {
                break StopReason::Cancelled;
            }
            if self.overflow(limit)? {
                break StopReason::OutputLimit;
            }
            if self.active()? == 0 {
                break StopReason::Exited(self.exit_code()?);
            }
            if self.started.elapsed() >= deadline {
                break StopReason::Deadline;
            }
            std::thread::sleep(Duration::from_millis(10));
        };
        let forced = !matches!(reason, StopReason::Exited(_));
        if forced {
            self.terminate()?;
        }
        let settled = self.settle(Duration::from_secs(5))?;
        let sizes = [
            fs::metadata(&self.stdout)?.len(),
            fs::metadata(&self.stderr)?.len(),
        ];
        if settled {
            for path in [&self.stdout, &self.stderr] {
                let file = OpenOptions::new().write(true).open(path)?;
                if file.metadata()?.len() > limit {
                    file.set_len(limit)?;
                }
            }
        }
        Ok(Completion {
            reason,
            forced,
            settled,
            captured_bytes_before_truncation: sizes,
        })
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum StopReason {
    Exited(u32),
    Deadline,
    Cancelled,
    OutputLimit,
}
#[derive(Debug)]
pub struct Completion {
    pub reason: StopReason,
    pub forced: bool,
    pub settled: bool,
    pub captured_bytes_before_truncation: [u64; 2],
}
impl Drop for Process {
    fn drop(&mut self) {
        let _ = self.terminate();
        let _ = self.settle(Duration::from_secs(5));
    }
}

pub fn publish(source: &Path, destination: &Path) -> io::Result<()> {
    let from = wide(source.as_os_str());
    let to = wide(destination.as_os_str());
    if unsafe { MoveFileExW(from.as_ptr(), to.as_ptr(), 0) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

pub fn locked_read(path: &Path) -> io::Result<File> {
    use std::os::windows::fs::OpenOptionsExt;
    OpenOptions::new()
        .read(true)
        .share_mode(windows_sys::Win32::Storage::FileSystem::FILE_SHARE_READ)
        .open(path)
}

pub fn pipe_owner(file: &File) -> io::Result<u32> {
    let mut pid = 0;
    if unsafe {
        windows_sys::Win32::System::Pipes::GetNamedPipeServerProcessId(
            file.as_raw_handle() as HANDLE,
            &mut pid,
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    Ok(pid)
}
pub fn pipe_available(file: &File) -> io::Result<u32> {
    let mut available = 0;
    if unsafe {
        windows_sys::Win32::System::Pipes::PeekNamedPipe(
            file.as_raw_handle() as HANDLE,
            std::ptr::null_mut(),
            0,
            std::ptr::null_mut(),
            &mut available,
            std::ptr::null_mut(),
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    Ok(available)
}
pub fn pipe_nonblocking(file: &File) -> io::Result<()> {
    let mode = windows_sys::Win32::System::Pipes::PIPE_NOWAIT;
    if unsafe {
        windows_sys::Win32::System::Pipes::SetNamedPipeHandleState(
            file.as_raw_handle() as HANDLE,
            &mode,
            std::ptr::null(),
            std::ptr::null(),
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::quote;
    #[test]
    fn command_line_quoting_preserves_spaces_quotes_and_trailing_slashes() {
        assert_eq!(quote(""), "\"\"");
        assert_eq!(quote("a b"), "\"a b\"");
        assert_eq!(quote("a\"b"), "\"a\\\"b\"");
        assert_eq!(quote("C:\\a b\\"), "\"C:\\a b\\\\\"");
        assert_eq!(quote("a\\\"b"), "\"a\\\\\\\"b\"");
    }
}
