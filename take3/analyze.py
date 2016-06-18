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
    A node in a graph. Has two kinds of successor nodes, 
    children and dependencies. 
    """
    def __init__(self, value, parent=None):
        self.value = value
        self.parent = parent #this is the scope wise parent
        self.children = {} 
        self.dependencies = {}

    def __repr__(self):
        return str(self.value)

    #TODO: remove the following since sets suck
    def __eq__(self, other):
        """
        Two vertices are the same if their values are the same.
        NOTE: __eq__, and __hash__ overidden so two objects get hashed to the same value
        """
        if isinstance(other, str):
            return self.value == other
        else: 
            return self.value == other.value

    def __hash__(self):
        return hash(self.value)
        


class DTree(object):
    """
    Something like a n-ary tree. Like tree, since each node 
    can have only one "parent". However, leafs can be connected to other leafs
    through a "depends-on" relationship. Basically, there are two kinds of edges
    ones that represent parent-child relationship, and ones that represent a
    dependency relationship.
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
                #Lazily build 
                current.children[node] = Vertex(node, parent=current)
            current = current.children[node]
        return current

    def add_link(self, src=None, dst=None):
        """
        Add a link from `src` path to `dst` path.
        These are lists of strings, indicating absolute
        paths starting at roots.
        """
        print "adding link = {}->{}".format(src, dst)
        srcleaf = self.add_path(src)
        dstleaf = self.add_path(dst)
        srcleaf.dependencies[str(dstleaf)] = dstleaf

    def write(self):
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



scopemap = namedtuple('Scopemap', ['scope', 'astnode'])
        
##################################################
######### Utilities (General) ####################
##################################################
#Types that create a scope
scoping_types = ["Module", "ClassDef", "FunctionDef"]

def create_and_raise(exception_name, exception_msg):
    """
    Creates a new Exception sub class and raises it.
    Arguments:
        exception_name:- name of exception class
        exception_msg: msg associated with exception
    """
    #Create exception
    ExceptionClass = type(exception_name, (Exception, ), {})
    #define __init__ method
    def exception__init__(self, message):
        super(ExceptionClass, self).__init__(message)
    ExceptionClass.__init__ = exception__init__

    #Now raise the exception
    raise ExceptionClass(exception_msg)

def concatenated(lst, element):
    """
    concatenates `element` to `lst`
    """
    lst.append(element)
    return lst

##################################################
################ Utilities #######################
##################################################

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

def set_src(node, srcmodule):
    """
    sets src module of ast `node`
    """
    setattr(node, "srcmodule", srcmodule)

def get_src(node):
    """
    Returns src module of node, None if attr not defined
    """
    return hasattr(node, "srcmodule") and getattr(node, "srcmodule") or None

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

def ast_name_node(**props):
    """
    creates a name ast node with the property names and values
    as specified in `props`
    """
    node = ast.Name()
    for name, value in props.items():
        setattr(node, name, value)
    return node

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
    print "Printing dependency tree*******************************"
    deptree.write() 
    print "*******************************************************"

def resolve_scope(match, candidates):
    """
    Returns the candidate in `candidates` that matches `match`.
    NOTE: candidate is an instance of scopemap
    The algorithm is this:
        -prune any invalid candidates, i.e. candidate must be a subset of match 
        -if there are multiple left, then check lineno.
    e.g. #here we would need lineno check to resolve foo

    def foo():
        pdb.set_trace()
    x = foo()
    def foo():
        return 11    

    """
    resolved = []
    for candidate in candidates:
        for i, node in enumerate(candidate.scope):
            if node != match[i]:
                break
        else:
            resolved.append(candidate)

    if len(resolved) == 1:
        return resolved[0]
    else: 
        create_and_raise("UnableToResolveException", "Unabled to resolve, setup the lineno tracking")
            
def get_children(node):
    """
    Returns list of children of ast `node`
    """
    return list(ast.iter_child_nodes(node))

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
    #creates mapping from name to scopes
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

        children = get_children(node) 
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
            symtable[identifier] = scopemap(scope=scopestack.get_state(), astnode=node)
        
        elif ntype == "Import":
            for name in node.names:
                identifier = name.asname or name.name
                #Set srcmodule property of ast node `name`
                set_src(name, name.name)
                #symtable mapping should contain the node itself
                symtable[identifier] = scopemap(scope=scopestack.get_state(), astnode=name)
        elif ntype == "ImportFrom":
            if node.names[0].name == '*':
                try:
                    imported = importlib.import_module(node.module)
                    #add all names in imported module, except those starting with '_'
                    for attr in dir(imported):
                        if attr[0] != '_':
                            symtable[attr] = scopemap(scope=scopestack.get_state(), 
                                                astnode=ast_name_node(name=attr, srcmodule=node.module))
                except ImportError:
                    print "Error: local system does not have {}. Skipping!".format(node.module)
            else:
                for name in node.names:
                    identifier = name.asname or name.name
                    set_src(name, name.name)
                    symtable[identifier] = scopemap(scope=scopestack.get_state(), astnode=name)

        elif ntype == "arguments":
            if node.vararg: 
                symtable[node.vararg] = scopemap(scope=scopestack.get_state(), astnode=node)
            if node.kwarg:
                symtable[node.kwarg] = scopemap(scope=scopestack.get_state(), astnode=node)

        #if a name is being loaded then it must already exist in symtable
        elif ntype == "Name" and not is_load(children) and not has_global(scopestack.get_tail(), node.id):
            symtable[node.id] = scopemap(scope=scopestack.get_state(), astnode=node)
    
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

    """
    
    deptree = DTree() 

    #stack of nodes
    nodes = Stack()
    nodes.push(root)

    #stack of scopes
    scopestack = Stack()

    for node in nodes:
        ntype = node_type(node)

        #remove stale scoping nodes
        scopestack.predpop(lambda scopenode: scopenode.depth >= node.depth)


        #TODO: should we also do the same stuff as create_symbol_table?

        if ntype == "Name": 
            #there is a dependency from scope -> name 
            if is_load(children):
                #we know a symbol was loaded, but since identifiers are non-unique, 
                #we must look up node in symtable and then resolve based on scopes
                current = scopestack.get_state()
                candidates = symtable[unique_id(node)]
                dependency = resolve_scope(current, candidates)
                #The deptree only maps identifiers
                
                deptree.add_link(map(unique_id, current), map(unique_id, dst), unique_id(node))

        elif ntype == "Attribute":
            #get the current scope
            current = scopestack.get_state()  
            #resolve the node based on the current scope
            candidates = symtable[unique_id(node)]  
            dependency = resolve_scope(current, candidates)
            
            srcmodule = get_src(dependency.astnode)
            if srcmodule:
                #if src module is not the same as the current module, then it should 
                #be a separate path emananting from root
                dst = [unique_id(node.value), node.attr]
            else:
                #dependency is intra-module
                dst = concatenated(map(unique_id, concatenated(dependency.scope, node.value)), node.attr)
            deptree.add_link(src = map(unique_id, current), dst = dst)
            #don't need to add children since we resolved the whole subtree here    
            #e.g. pdb.set_trace, is an Attribute node with children value (Name= pdb) and attr (str = 'set_trace')
            #adding the child Name node could lead to redundant (incorrect) dependencies
            continue            
 
        #push nodes onto the stack; depth is already set from create_symbol_tree()
        #needs to be done here since not all children need to put on stack
        children = get_children(node) 
        nodes.pushmany(reversed(children))

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
    #The alternative approach would be to have one pass, and resolve symbols as 
    #soon as they become available; however, existing solution is closer to how Python works
    symbol_table = create_symbol_table(root)
    print_symtable(symbol_table)

    #find dependencies
    dependency_tree = create_dependency_tree(root, symbol_table)
    #print_deptree(dependency_tree)

"""
How best to represent dependencies?
Think in terms of eventual goal of this proj, e.g. graphDB, query engine, visualization etc.

1) Dependency as a (src, dest) where src is the source is the dependent code block 
and dest is the independent code block.

2) Dependency tree where leaf is the dest of depend, and branch to leaf is the src.

===================================
TODO: 
1) Keep track of returns 

2) assignments

3) Keep track of lineno, lineno_end of a node, to resolve the following, 
ie. does bar dependend on pdb, or requests?

#foo.py
import pdb, requests
def foo():
    pdb.set_trace()
f = foo()
def foo()
    request.get()

#bar.py
from foo import foo
x = foo()

Obviously this can't catch monkey typing etc., but 
hopefully that isn't a big concern if most code bases

4) Above example, does bar depend on pdb or requests?
    -to resolve the above issue __hash__, __eq__ of Vertex should consider lineno

5) Nodes (vertices) should have ptrs to parents?
"""


if __name__ == "__main__":
    analyze('test.py')

