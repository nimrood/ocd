from collections import defaultdict
from itertools import dropwhile, permutations

graphfile = None

class Graph:
    def __init__(self):
        self._pred = defaultdict(list)
        self._succ = defaultdict(list)
        self._vertices = {}

    def __str__(self):
        return 'Graph(vertices=' + str(self._vertices) + ', pred=' + str(self._pred) + ', succ=' + str(self._succ) + ')'

    def __contains__(self, (v, t)):
        if t == 'in':
            return (v in self._pred)
        if t == 'out':
            return (v in self._succ)
        if t == None:
            return (v in self._pred or v in self._succ)

    def successors(self, key):
        return self._succ[key]

    def predecessors(self, key):
        return self._pred[key]

    def vertex(self, k):
        return self._vertices[k]

    def set_vertex(self, k, v=None):
        self._vertices[k] = v

    def remove_vertices(self, ks):
        for k in ks:
            for p in self._pred[k]:
                self._succ[p].remove(k)
            for s in self._succ[k]:
                self._pred[s].remove(k)
            del self._pred[k]
            del self._succ[k]
            del self._vertices[k]

    def vertices(self):
        return self._vertices

    def deg_in(self, k):
        return len(self._pred[k])

    def deg_out(self, k):
        return len(self._succ[k])

    def add_edge(self, v_in, v_out):
        self._succ[v_in].append(v_out)
        self._pred[v_out].append(v_in)

    def remove_edge(self, v_in, v_out):
        self._succ[v_in].remove(v_out)
        self._pred[v_out].remove(v_in)

    def export(self, f, name, random=False):
        def block_label(block_type, block_loc, block):
            if block_type == 'block':
                return "block\\n{0:x}:{1:x}".format(block_loc, block[-1]['loc'])
            else:
                return "{0}\\n{1:x}".format(block_type, block_loc)

        if random:
            import random
            name += '_'+''.join(random.sample('0123456789abcdef', 8))

        f.write("\tsubgraph {0} {{\n".format(name))

        entries = filter(lambda k: self.deg_in(k) == 0, self.vertices())

        f.write("\t\t{0}_entry [label=\"{0}\"];\n".format(name))
        for e_type, e_loc in entries:
            f.write("\t\t{0}_entry -> {0}_{1}_{2:x};\n".format(name, e_type, e_loc))

        for (block_type, block_loc), block in self.vertices().iteritems():
            f.write("\t\t{0}_{1}_{2:x} [label=\"{3}\"];\n".format(name, block_type, block_loc, block_label(block_type, block_loc, block)))
            for v_type, v_out in self.successors((block_type, block_loc)):
                f.write("\t\t{0}_{1}_{2:x} -> {0}_{3}_{4:x};\n".format(name, block_type, block_loc, v_type, v_out))
        f.write("\t}\n")       

def control_flow_graph(function, labels, name):
    '''
    Analyze the control flow graph (cfg) of the function
    '''

    graph = Graph()
    block_acc = []
    block_cur = None
    block_last = None
    block_change = True
    pass_through = False
    for ins in function:
        if ins['loc'] in labels or block_change:
            if block_last is not None:
                graph.set_vertex(block_last, block_acc)
            block_cur = ('block', ins['loc'])
            block_acc = []
            graph.set_vertex(block_cur)

        if ins['loc'] in labels and pass_through:
            # pass-through edge
            graph.add_edge(block_last, ('block', ins['loc']))

        block_change = False
        pass_through = True

        if ins['ins'][0][0] == 'j': # jumps (and only jumps)
            loc_next = ins['loc']+ins['length']
            loc_j = loc_next+int(ins['ins'][1], 16)
            graph.add_edge(block_cur, ('block', loc_j))
            block_change = True
            if ins['ins'][0] != 'jmp':
                graph.add_edge(block_cur, ('block', loc_next))
            else:
                pass_through = False
        block_last = block_cur
        block_acc.append(ins)

    graph.set_vertex(block_last, block_acc)
  
    if graphfile:
        graph.export(graphfile, name)

    return graph_transform(graph)

def flip(x):
    '''
    flip(x)(f) = f(x)
    '''
    def f(g):
        return g(x)
    return f

def graph_transform(graph):
    '''
    Perform one step transformations of the graph according to
     preset rules until no more transformations can be performed.

    The rewriting system used here is decreasing (i.e. all transformations
     decrease the size of the graph), because every transformation rule is
     guaranteed to be decreasing, therefore it is total (it will always stop
     at some point.

    Transformation rules are functions of the type

      Graph -> (Boolean, Graph)

    The boolean value signifies whether the transformation condition was
     satisfied and the transformation was applied successfully.

    If no further transformation can be performed, the process is stopped
     and the resulting graph is returned.
    '''
    def t_trivial(graph):
        return False, graph

    def t_while(graph):
        for v in graph.vertices():
            if graph.deg_out(v) == 2:
                succs = graph.successors(v)
                for s1, s2 in permutations(succs):
                    if graph.deg_out(s1) == 1 and graph.deg_in(s1) == 1 and v in graph.successors(s1):
                        v_type, v_start = v
                        v_new = ('while', v_start)
                        condition = 'cmp'
                        v_new_value = (condition, (v, graph.vertex(v)), (s1, graph.vertex(s1)))
                        graph.set_vertex(v_new, v_new_value)
                        for pred in graph.predecessors(v):
                            graph.add_edge(pred, v_new)
                        graph.add_edge(v_new, s2)
                        graph.remove_vertices([v,s1])
                        
                        return (True, graph)

        return (False, graph)

    def t_if(graph):
        for v in graph.vertices():
            if graph.deg_out(v) == 2:
                succs = graph.successors(v)
                for s1, s2 in permutations(succs):
                    if graph.deg_out(s1) == 1:
                        s1_succ = graph.successors(s1)[0]
                        if s1_succ == s2:
                            s1_type, s1_start = s1
                            v_new = ('if', s1_start)
                            condition = 'cmp'
                            v_new_value = (condition, (s1, graph.vertex(s1)))
                            graph.set_vertex(v_new, v_new_value)
                            graph.add_edge(v, v_new)
                            graph.add_edge(v_new, s2)
                            graph.remove_edge(v, s2)
                            graph.remove_vertices([s1])
                            return (True, graph)

        return (False, graph)

    def t_ifelse(graph):
        for v in graph.vertices():
            succs = graph.successors(v)
            if len(succs) == 2:
                s, t = succs
                s_s, t_s = map(graph.successors, succs)
                s_p, t_p = map(graph.predecessors, succs)
                if map(len, [s_s, t_s, s_p, t_p]) == [1]*4 and s_s == t_s:
                    s_type, s_start = s
                    v_new = ('ifelse', s_start)
                    condition = 'cmp' # change that
                    # modify v
                    v_new_value = (condition,
                        (s, graph.vertex(s)), (t, graph.vertex(t)))
                    graph.set_vertex(v_new, v_new_value)
                    graph.add_edge(v_new, s_s[0])
                    graph.add_edge(v, v_new)
                    graph.remove_vertices([s, t])
                    return (True, graph)

        return (False, graph)

    def t_cons(graph):
        for v in graph.vertices():
            if graph.deg_out(v) == 1:
                s = graph.successors(v)[0]
                if graph.deg_in(s) == 1 and v != s:
                    v_type, v_start = v
                    s_type, s_start = s
                    if v_type == 'cons':
                        graph.vertex(v).append((s, graph.vertex(s)))
                        #graph.set_vertex(v, v_value)
                        for succ in graph.successors(s):
                            graph.add_edge(v, succ)
                        graph.remove_vertices([s])
                    else:
                        v_new = ('cons', v_start)
                        v_new_value = [(v, graph.vertex(v)), (s, graph.vertex(s))]
                        graph.set_vertex(v_new, v_new_value)
                        for pred in graph.predecessors(v):
                            graph.add_edge(pred, v_new)
                        for succ in graph.successors(s):
                            graph.add_edge(v_new, succ)
                        graph.remove_vertices([v,s])
                    return (True, graph)

        return (False, graph) 

    rules = [t_trivial, t_ifelse, t_cons, t_if, t_while]

    i = dropwhile(lambda (x, y): not x, map(flip(graph), rules))
    try:
        true, graph = i.next()
        if graphfile:
            graph.export(graphfile, 'step', random=True)
        return graph_transform(graph)
    except StopIteration:
        if graphfile:
            graph.export(graphfile, 'transformed')
        return graph
