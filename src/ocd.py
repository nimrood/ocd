#!/usr/bin/env python3
from disassemble import disassemble
from decompile import decompile_functions
import control_flow
import debug
import representation

from subprocess import Popen, PIPE

def objdump(filename):
    p1 = Popen(["objdump", "-h", filename], stdout=PIPE)
    p2 = Popen(["awk", "-f", "src/sections.awk"], stdin=p1.stdout, stdout=PIPE)
    sections_p = p2.communicate()[0].split()

    p1 = Popen(["objdump", "-t", filename], stdout=PIPE)
    p2 = Popen(["awk", "-f", "src/symbols.awk"], stdin=p1.stdout, stdout=PIPE)
    #symbols_p_raw = p2.communicate()[0]
    #print(type(symbols_p_raw))
    symbols_p = p2.communicate()[0].decode().split('\n')

    text = {'start': int(sections_p[0], 16), 'length': int(sections_p[1], 16), 'virt': int(sections_p[2], 16)}
    symbols = {}
    for symbol_p in symbols_p[:-1]:
        symbol = symbol_p.split()
        symbols[symbol[0]] = {'start': int(symbol[1], 16), 'length': int(symbol[2], 16)}

    return text, symbols

if __name__=="__main__":
    import sys
    from optparse import OptionParser

    usage = "usage: %prog [options] file"
    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--debug", dest="debug", action="append",
        help="turn debug option on", default=[], choices=debug.options,
        metavar="OPTION")
    parser.add_option("-g", "--graph", action="store", dest="graphfile",
        metavar="FILE", type="string", help="output a control flow graph")

    options, args = parser.parse_args()

    for option in options.debug:
        debug.set(option)    

    if len(args) < 1:
        parser.print_help()

        sys.exit(0)

    filename = args[0]

    f = open(filename, "rb")

    text, symbols = objdump(filename)

    if options.graphfile:
        gf = open(options.graphfile, 'w')
        gf.write("digraph cfg {\n")
        control_flow.graphfile = gf


    functions = {}
    if symbols:
        for name, symbol in symbols.items():
            f.seek(symbol['start']-text['virt']+text['start'])
            functions[name] = disassemble(f.read(symbol['length']), symbol['start'])
    else:
        f.seek(text['start'])
        functions['start'] = disassemble(f.read(text['length']), text['virt'])
        symbols['start'] = {'start': text['virt'], 'length': text['length']}

    decompiled_functions = decompile_functions(functions, symbols)

    print(representation.output_functions(decompiled_functions))

    if options.graphfile:
        gf.write("}\n")
        gf.close()