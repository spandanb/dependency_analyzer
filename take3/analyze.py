"""
Rewrite of analyze.py
"""
import ast
import pdb
from utils import get_module, node_type, pretty_print, unique_id, nodes_to_str
from collections import namedtuple
import importlib

##################################################
############# Datastructures #####################
##################################################
class Multidict(dict):
    """
    Implements a hashmap like data structure where keys are mapped to 
    a list of items.
    """
    def __init__(self, *args, **kw):
        super(Multidict, self).__init__(*args, **kw)

    def __setitem__(self, key, value):
        if not key in self:
            #Lazily creates mapping of keys to list of values
            super(Multidict, self).__setitem__(key, [value])
        else: 
            self[key].append(value)

class Stack(list):
    """
    Implements a stack with some additional utility functions.
    """
    def __init__(self, *args, **kw):
        super(Stack, self).__init__(*args, **kw)

    def push(self, item):
        "Push an item onto the stack"
        super(Stack, self).append(item)

    def pushmany(self, items):
        "Push many items onto the stack"
        super(Stack, self).extend(items)
        
    def predpop(self, predicate):
        """
        pops all tail elements if predicate is true.
        Returns the list of popped elements
        """
        popped = []
        while self.__len__():
            if predicate(self[-1]):
                popped.append(super(Stack, self).pop())
            else:
                break
        return popped

    def get_state(self):
        """Returns a copy of this object. 
        """
        return self[:] 
    
    def get_tail(self):
        "Returns the tail element."
        return self[-1]

    def __iter__(self):
        return self

    def next(self):
        if not self.__len__():
            raise StopIteration
        else:
            return self.pop()

class Vertex(object):
    """
    A node in a graph 
    """
    def __init__(self, value):
        self.value = value
        self.children = {}

    def __repr__(self):
        return str(self.value)

    def __cmp__(self, other):
        #FIXME: doesn't work, do we need __hash__ as well?
        #TODO: add __cmp__, __hash__ so that children can be a set(), instead of mapping name string to DNode obj
        return self.value == other.value


class Dag(object):
    """
    Recursive n-ary DAG.
    Everything is the child of the root
    """
    def __init__(self): 
        self.root = Vertex(None) 
    
    def add_path(self, path):
        """
        Adds path to the DAG
        Args:- 
            path: list of nodes
        Returns last node in `path`
        """
        current = self.root
        for node in path:
            if node not in current.children:
                #Lazily build tree
                current.children[node] = Vertex(node)
            current = current.children[node]
        return current

    def print_tree(self):
        """
        This method is a wrapper around incrementally increasing
        BFS calls.
        Used for debugging
        """
        def get_nodes(node, depth):
            """
            This is a helper method that gets nodes at specified depth.

            Arguments:-
            node:- the starting node
            depth:- the number of generations down from `node`
            """
            if depth == 0:
                return [node.value]
            else:
                nodes = []
                for child in node.children.values():
                    nodes.extend(get_nodes(child, depth-1))
                return nodes

        depth = 0
        while True:
            nodes = get_nodes(self.root, depth)
            if not nodes: break
            print nodes
            depth += 1


    def add_link(self, src, dst, connect):
        """
        Add a link from `src` path to `dst` path.
        These are lists of strings, indicating absolute
        paths starting at roots.
        `connect` is the node that src references
        """
        srcleaf = self.add_path(src)
        dst.extend(connect)
        destleaf = self.add_path(dst)
        srcleaf.children[connect] = destleaf

        
        

#Used as the value in symbol table
#TODO: Does astnode need to be stored?
#TODO: remove
scopemap = namedtuple('ScopeMap', ['astnode', 'scope'])

##################################################
################ Utilities #######################
##################################################
#Types that create a scope
scoping_types = ["Module", "ClassDef", "FunctionDef"]

def set_depth(node, depth):
    """Set the depth of an AST node
    """
    setattr(node, "depth", depth)

def set_globals(node, identifiers):
    """
    set list of identifiers as 'globals' on node
    """
    if not hasattr(node, "globals"):
        setattr(node, "globals", [])
    node.globals.append(identifiers)

def has_global(node, identifier):
    """
    check whether node has identfier in its globals list
    """
    return hasattr(node, "globals") and name in node.globals

def is_load(children):
    """
    Called on the children nodes of "Name" node.
    Determines if node is being loaded
    """
    return children and node_type(children[0]) == "Load"

def is_store(children):
    return children and node_type(children[0]) == "Store"

def set_lineno(node, children):
    """
    Sets lineno and lineno_end of all children of `node`.
    Assigns lineno_end of ith child as the
    the lineno of i+1 th child. 
    
    Some AST nodes don't have a `lineno` property;
    in these cases sets it based on the following algorithm.
    """
    for i, child in enumerate(children):
        #if child does not have lineno, add it 
        if not hasattr(child, "lineno"):
            setattr(child, "lineno", node.lineno)

        if i == len(children) - 1:
            #set child's lineno_end to node's lineno    
            setattr(child, "lineno_end", node.lineno_end)
        else:
            sibling = children[i+1][0]
            #if next sibling does not have lineno, add it
            if not hasattr(sibling, "lineno"):
                setattr(sibling, "lineno", node.lineno)

            #set child's lineno_end to next sibling's lineno-1
            #unless that would make it less than child's lineno
            setattr(child, "lineno_end", max(child.lineno, sibling.lineno - 1))

def print_symtable(symtable):
    """
    prints symbol table
    """
    print "Printing symbol table *********************************"
    for key, value in symtable.items():
        print "{}:".format(key)
        for val in value:
            print "    {}".format(nodes_to_str(val.scope))
    print "*******************************************************"

def print_deptree(deptree):
    pass

def resolve_scope(match, candidates):
    """
    Returns the candidate in `candidates` that matches `match`.
    The algorithm is this:
        -prune any invalid candidates, i.e. if the candidate does not share ancestors scopes
        -if there are multiple left, then check lineno.
    e.g. #here we would need lineno check

    def foo():
        pdb.set_trace()
    x = foo()
    def foo():
        return 11    

    """
    for candidate in candidates:

##################################################
################    Main   #######################
##################################################

def create_symbol_table(root):
    """
    Creates a symbol table.
    Arguments:-
        root: root ast node to be analyzed (typically a module node).
    """

    #symbol table
    #creates mapping from name to scopenode, i.e. (scopes, astnode)
    symtable = Multidict()
    
    #stack of nodes
    nodes = Stack()
    set_depth(root, 0)
    nodes.push(root)
    
    #stack of scopes
    scopestack = Stack()

    #Iterate over all children node
    for node in nodes:
        ntype = node_type(node)
        
        #remove any scope nodes that have depth >= node 
        scopestack.predpop(lambda scopenode: scopenode.depth >= node.depth)

        children = list(ast.iter_child_nodes(node))
        #add children to stack in reverse order
        for child in reversed(children):
            #set depth on children nodes
            set_depth(child, node.depth + 1)
            nodes.push(child)
        #set lineno property of children
        #Not sure if there is a better way to scope objects, since 
        #objects can be redefined, i.e. def foo(): pass\n def foo():pass is valid Python
        #set_lineno(node, children)
   
        #add entries to symbol table
        if ntype == "ClassDef" or ntype == "FunctionDef":
            identifier = unique_id(node)
            symtable[identifier] = scope=scopestack.get_state()
        
        elif ntype == "Import":
            for name in node.names:
                identifier = name.asname or name.name
                symtable[identifier] = scope=scopestack.get_state()

        elif ntype == "ImportFrom":
            if node.names[0].name == '*':
                try:
                    imported = importlib.import_module(node.module)
                    #add all names in imported module, except those starting with '_'
                    for attrs in dir(imported):
                        if attrs[0] != '_':
                            symtable[attrs] = scope=scopestack.get_state()
                except ImportError:
                    print "Error: local system does not have {}. Skipping!".format(node.module)
            else:
                for name in node.names:
                    identifier = name.asname or name.name
                    symtable[identifier] = scope=scopestack.get_state()

        elif ntype == "arguments":
            if node.vararg: 
                symtable[node.vararg] = scope=scopestack.get_state()
            if node.kwarg:
                symtable[node.kwarg] = scope=scopestack.get_state()

        #if a name is being loaded then it must already exist in symtable
        elif ntype == "Name" and not is_load(children) and not has_global(scopestack.get_tail(), node.id):
            symtable[node.id] = scope=scopestack.get_state()
    
        elif ntype == "Global":    
            #add a list global vars on node on the top of scope stack
            #nonlocal could be handled in similar way
            #FIXME: ensure this is correct
            set_globals(scopestack.get_tail(), node.names)
            
        #add any scoping nodes 
        #Need to do this after ntype == '...' blocks otherwise scoping nodes
        #would show up in their own scope mapping. 
        if ntype in scoping_types: 
            scopestack.push(node)

    return symtable

def create_dependency_tree(root, symtable):
    """
    Returns a map of all the dependencies.

    Similar to create_symbol_table since scopes are some what
    like dependencies, minus the hierarchical scope info.
    ===============

    Keep track of returns and assignments

    """
    
    deptree = Dag() 

    #stack of nodes
    nodes = Stack()
    nodes.push(root)

    #stack of scopes
    scopestack = Stack()

    for node in nodes:
        ntype = node_type(node)

        #remove stale scoping nodes
        scopestack.predpop(lambda scopenode: scopenode.depth >= node.depth)

        #push nodes onto the stack; depth is already set from create_symbol_tree()
        children = list(ast.iter_child_nodes(node))
        nodes.pushmany(reversed(children))

        if ntype == "Name": 
            #there is a dependency from scope -> name 
            if is_load(children):
                #we know a symbol was loaded, but since identifiers are non-unique, 
                #we must look up node in symtable and then resolve based on scopes
                current_scope = 
                src = scopestack.get_state()
                
                dst = resolve_scope(scopestack.get_state(), symtable[unique_id(node)])
                dst = map(unique_id, dst)
                deptree.add_link(src, dst, unique_id(node))

        if ntype in scoping_types: 
            scopestack.push(node)

    return deptree

def analyze(filepath):
    """
    Analyze the module pointed by `filepath`
    """

    #Get module as ast node
    root = get_module(filepath)

    #create symbol table
    #The symbol table creation must be a separate phase from dependency tree creation 
    #since Python does not evaluate, e.g. Functions on parse. Therefore, entities can be used before
    #being defined.
    symbol_table = create_symbol_table(root)

    #print_symtable(symbol_table)

    #find dependencies
    dependency_tree = create_dependency_tree(root, symbol_table)
    print_deptree(dependency_tree)

"""
How best to represent dependencies?
Think in terms of eventual goal of this proj, e.g. graphDB, query engine, visualization etc.

1) Dependency as a (src, dest) where src is the source is the dependent code block 
and dest is the independent code block.

2) Dependency tree where leaf is the dest of depend, and branch to leaf is the src.

"""


if __name__ == "__main__":
    analyze('test.py')






