# Feature specification catalog

All specifications are initial proposals, not reviewed or implemented behavior. Requirement IDs remain stable as details are refined.

| Feature | Goal |
| --- | --- |
| [Kernel and exceptions](kernel.md) | Integrate startup and diagnose kernel faults |
| [Memory management](mm.md) | Allocate memory and isolate address spaces |
| [Task scheduling](sched.md) | Run multiple tasks with correct saved execution state |
| [Filesystem](fs.md) | Offer consistent file access and eventual persistence |
| [Interprocess communication](ipc.md) | Exchange data between isolated tasks |
| [Syscall boundary and executable loading](syscall.md) | Allow controlled requests from user programs |
| [Hardware abstraction](hal.md) | Separate portable services from device-specific operations |
| [Pi Zero 2 W board support](bsp.md) | Describe board resources and establish boot assumptions |
| [Block storage driver](block.md) | Read and write storage using bounded device requests |
| [Console driver](console.md) | Provide serial output and interactive input |
| [GPIO driver](gpio.md) | Control supported pins with explicit ownership |
| [Timer driver](timer.md) | Supply timekeeping and timer events |
| [Init process](init.md) | Start and supervise the first user environment |
| [Interactive shell](shell.md) | Parse commands and launch supported programs |
| [Command-line utilities](utils.md) | Provide a deliberately small useful command set |
| [C runtime startup](crt.md) | Start and terminate C user programs correctly |
| [C library subset](libc.md) | Implement the C interfaces required by selected programs |
| [MicroPython integration](micropython.md) | Run a bounded interpreter port and examples |
| [Build foundation and image builder](image-builder.md) | Produce inspectable kernel artifacts and reproducible boot media |
| [Program and asset packaging](packager.md) | Package programs with compatible metadata and runtime assets |
