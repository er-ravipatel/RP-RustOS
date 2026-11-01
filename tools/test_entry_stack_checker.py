"""Adversarial checks for the conservative linked stack analyzer."""
import unittest
from check_entry_stack import analyze


class StackCheckerTests(unittest.TestCase):
    def run_code(self, code, extra=()):
        functions = {0: {'name': 'root', 'address': 0, 'size': len(code)*4}}
        instructions = {i*4: instruction for i, instruction in enumerate(code)}
        for address, body in extra:
            functions[address] = {'name': f'callee{address}', 'address': address, 'size':len(body)*4}
            instructions.update({address+i*4:instruction for i,instruction in enumerate(body)})
        return analyze(functions, instructions, {'root':0}, 0x1000)[0]['root'][0]

    def test_call_and_tail_are_conservative(self):
        child = [('stp','x29, x30, [sp, #-0x10]!'),('ldp','x29, x30, [sp], #0x10'),('ret','')]
        code = [('sub','sp, sp, #0x20'),('bl','#0x100'),('add','sp, sp, #0x20'),('ret','')]
        self.assertEqual(self.run_code(code,[(0x100,child)]),48)
        tail = [('sub','sp, sp, #0x20'),('add','sp, sp, #0x20'),('b','#0x100')]
        self.assertEqual(self.run_code(tail,[(0x100,child)]),48)

    def test_unsupported_paths_rejected(self):
        cases = [ [('sub','sp, sp, x9'),('ret','')],
                  [('sub','sp, sp, #0x10'),('b','#0x0')],
                  [('add','sp, sp, #0x10'),('b','#0x0')],
                  [('blr','x9'),('ret','')], [('bl','#0x0'),('ret','')],
                  [('b','#0x200')], [('str','x0, [sp, #-0x8]'),('ret','')],
                  [('mov','wsp, w9'),('ret','')], [('ret','x9')],
                  [('sub','sp, sp, #0x10'),('ret','')],
                  [('ldr','x0, [sp], x9'),('ret','')],
                  [('nop','')] ]
        for code in cases:
            with self.subTest(code=code), self.assertRaises((ValueError,KeyError)):
                self.run_code(code)

    def test_returning_final_call_rejected(self):
        with self.assertRaises(ValueError):
            self.run_code([('bl','#0x100')],[(0x100,[('ret','')])])

    def test_noreturn_panic_tail_allowed(self):
        self.assertEqual(self.run_code([('sub','sp, sp, #0x20'),('bl','#0x100')],
                                      [(0x100,[('b','#0x1000')])]),32)

    def test_only_explicit_terminal_set_is_accepted(self):
        functions={0:{'name':'root','address':0,'size':8}}
        instructions={0:('cbz','w0, #0x1000'),4:('b','#0x2000')}
        results,_=analyze(functions,instructions,{'root':0},{0x1000:'ready',0x2000:'failed'})
        self.assertEqual(results['root'][0],0)
        with self.assertRaises(ValueError):
            analyze(functions,instructions,{'root':0},{0x1000:'ready'})


if __name__ == '__main__':
    unittest.main()
