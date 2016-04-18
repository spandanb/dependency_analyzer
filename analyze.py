"""
This module contains the functions and classes that analyze
the code or directly help in the analysis.
"""
import ast
import pprint
from sets import Set
import json
import os.path
import consts
from hashlist import hashlist
import sys
import pdb

def get_module(filepath):
    """
    Returns a AST node object corresponding to argument file.
    In addition sets `lineno` and `lineno_end` for starting and 
    ending line number (inclusive).
    
    Arguments:- filepath
        name of file to converted

    Return: AST node object
    """
    with open(filepath, "r") as f:
        lines = f.readlines()
        src  = "".join(lines)
    
    node = ast.parse(src)
    #Sets the start and end line numbers
    node.lineno = 1
    node.lineno_end = len(lines)

    return node

def pretty_print(self_map):
    pprint.pprint(self_map)
    #print json.dumps(self_map, sort_keys=True, indent=2)

#Returns type of AST node
node_type = lambda node: node.__class__.__name__

def unique_id(node):
    """
    Returns progressively less informative identifiers
    """
    ntype = node_type(node)

    identifier = ''

    if ntype == 'Str':
        identifier = node.s
    elif ntype == 'Num':
         identifier = node.n
    elif ntype == 'Call' and hasattr(node.func, 'id'):
         identifier = node.func.id
    elif ntype == 'Attribute':
        identifier = node.value.id
    elif ntype == 'Import':
        identifier = node.names[0].name
    elif ntype == 'ImportFrom':
        identifier = node.module
    elif ntype == 'Module':
        identifier = node.name
    else:
        identifier = getattr(node, "name", 
                getattr(node, "id",
                    id(node) 
                )
            )
    return str(identifier)


class NodeVisitor(ast.NodeVisitor):
    """Class that implements NodeVisitor functionality
    The methods visit and generic_visit are adapted from ast.py in the 
    std distribution.
    
    The attributes i.e. name, arg, decorators etc. are 
    properties of the node obj. The attributes vary depending on
    the specific node obj, i.e. a function has an arg, whereas a 
    class does not.
    
    """ 
    def visit(self, node, node_map):
        """
        Visits children node.
        If visitor method does not exist, calls generic visit
        i.e. the `visitor` is a reference to a function pointing 
        to either visit_FOO(...) or generic_visit(...)

        Arguments: 
            node: the node to visit
            node_map: a 2-list where the first element is
                the node itself, and the second element is a list of its 
                children's `node_map` (i.e. defined recursively)
        """
        node_type = node.__class__.__name__
        method = 'visit_' + node_type 
        visitor = getattr(self, method, self.generic_visit)
        
        return visitor(node, node_map)

    def generic_visit(self, node, parent_map):
        """Called if no explicit visitor function exists for a node.
        Arguments:-
            node (AST Node)- the AST node to visit
            node_map (list)- this node's map, contains descendents
        """
        node_map = []
        parent_map.append((node, node_map))
       
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item, node_map)
            elif isinstance(value, ast.AST):
                self.visit(value, node_map)

def name_from_path(path):
    """Returns name of a module given its path,
        i.e. strips '.py' """
    return path[0:-3]

def symbolic_pretty_print(nodes):
    """
    Pretty prints the unique_id and node type
    instead of nonsense __repr__ of node
    """
    def symbify(nodes):
        """
        get representation of nodes
        where each element is represented by
        its unique id
        """
        if not nodes: return None
        
        root, children = nodes
        return [(unique_id(root), node_type(root)), 
                    [symbify(child) for child in children]]

    pretty_print(symbify(nodes[0]))

        
def is_load(children):
    """
    Returns whether children has Load op
    Note: children[0] indexes to first child, 
    children[0][0] indexes to node 
    """
    return children and node_type(children[0][0]) == "Load"

def is_store(children):
    return children and node_type(children[0][0]) == "Store"


def scopes_to_str(scopes):
    """
    Converts a scopes' stack to string
    """
    return '.'.join(map(unique_id, scopes))
    

def handle_name(node, children, scopes):
    #check for loads
    if is_load(children):
        print "{} => {}".format(scopes_to_str(scopes), unique_id(node))

###############################################################
#####################      TODO     ###########################
#1)
#Use a class: There is too much state that needs to be managed

#2)
# stack.pop() takes the last item
#but items are added in the opposite order

#3)
#Handle function parameters
###############################################################

"""
These setters and getter exists
in case the data structure of node is changed
"""
def set_depth(node, depth):
    """Set the depth of an AST node
    """
    setattr(node[0], "depth", depth)

def set_lineno_end(node, lineno_end):
    """Set lineno end of an AST node
    """
    setattr(node[0], "lineno_end", lineno_end)

def get_lineno(node):
    """
    Get's the lineno of the node
    """
    return node[0].lineno

def set_globals(node, names):
    """
    sets global names. Lazily adds property
    """
    if not hasattr(node, "globals"):
        setattr(node, "globals", [])

    node.globals.extend(names)

def has_global(node, name):
    """
    check whether node has name in its globals list
    """
    return hasattr(node, "globals") and name in node.globals

#These are the node types that create a scope
#global and nonlocal vars need to tracked separately
scoping_nodes = ["Module", "ClassDef", "FunctionDef"]

def create_symbol_table(root):
    """
    Creates a symbols table that maps each
    symbol to the scope within which it occurs.

    Similar to find_dependencies in terms of traversing
    the AST.
    TODO: refactor common stuff into separate function

    The data structure used is a hashtable where 
    names are mapped to list of scopes, i.e. a hashlist. 

    The scope can be precisely defined in terms of 
    lineno range. The alternative is to define as scope
    as, e.g. <module name>.<function name> but this can lead 
    to ambiguity since the functions etc. can be redefined.
    Also the lineno approach relies on the beginning lines
    of siblings which can lead to a larger range than actually is 
    due to whitespaces. This gets tricky because functions can 
    be used before they are defined, but not variables.  
    """

    set_depth(root, 0)
    stack = [root]

    scopes = [] 

    symbol_table = hashlist()

    while stack:
        node, children = stack.pop()
        ntype = node_type(node) 

        #remove any stale scopes
        while len(scopes):
            #check `depth` of closest scope    
            if node.depth <= scopes[-1].depth:
                scopes.pop()
            else:
                break
        
        if ntype == "Import":
            #Import object has names prop which
            #is an array of names
            for name in node.names:
                #name can be the name or an alias   
                name_val = name.asname or name.name
                #insert in symbol_table                
                symbol_table[name_val] = (scopes[-1].lineno, scopes[-1].lineno_end)

        elif ntype == "ImportFrom":
            if node.names[0].name == '*':
                #TODO: lookup members of this module
                pass
            else:
                for name in node.names:
                    name_val = name.asname or name.name
                    symbol_table[name_val] = (scopes[-1].lineno, scopes[-1].lineno_end)

        elif ntype == "ClassDef" or ntype == "FunctionDef":   
            symbol_table[node.name] = (scopes[-1].lineno, scopes[-1].lineno_end)
        
        #NOTE: if a name is being loaded then it already exists and doesn't need
        #to be added to symbol_table
        elif ntype == "Name" and not is_load(children) and not has_global(scopes[-1], node.id): 
            symbol_table[node.id] = (scopes[-1].lineno, scopes[-1].lineno_end)

        elif ntype == "arguments":
            if node.vararg: 
                symbol_table[node.vararg] = (scopes[-1].lineno, scopes[-1].lineno_end)
            if node.kwarg:
                symbol_table[node.kwarg] = (scopes[-1].lineno, scopes[-1].lineno_end)

        elif ntype == "Global":
            #add a list global vars on node on the top of  
            #the stack
            #NOTE: nonlocal could be handled in similar way
            set_globals(scopes[-1], node.names)

        for i, child in enumerate(children):
            #set depth of child
            set_depth(child, node.depth + 1)
            
            #set lineno_end of child
            #TODO: this only needs to be done for scoping_nodes
            if i == len(children) - 1:
                set_lineno_end(child, node.lineno_end)
            else:
                set_lineno_end(child, get_lineno(children[i+1]) - 1)

        #Add children to stack
        #Need to do this separately since children must be 
        #added in reverse order 
        stack.extend(children[::-1])

        #Add any new scopes
        #Need to do it here since scoping_nodes are defined in their parent scope
        if ntype in scoping_nodes:
            scopes.append(node)

    print symbol_table
    return symbol_table
    

def find_dependencies(root):
    """
    Finds all dependencies in root object. 
    Whereas check_dependency checks for dependencies to 
    top level objects, this checks all dependencies.

    Create a symbol-scope table. 
    Note, python has local, nonlocal, and global scopes

    TODO: This function is doing two tasks: 1) creating a symbols-scope
    table and 2) finding dependencies based on this. 
    However, the first has to be done in its entirety first
    since entities (functions, classes) can be referenced before they are
    defined. 

    Cases (nodes) to account for:
        1) Assign 
            -check for the Name being assigned
        2) Name being invoked
            -here it makes sense to search for name
        3) Attribute
            e.g. pdb.set_trace(), set_trace is an attribute of pdb
            -see check dependency
        4) Import
            These are needed when building a symbols table
        5) ImportFrom
            ibid
            
    Gotchas:
        1) a name being stored
            i.e. a name collisions that makes it seem like
            a dependency exists
        2) x = y = z = 3
        3) Attribute chains can be arbitrarily long
            x.y.z,
            or x().y().z(),
            or some combination thereof

    Consider a dependecy as containing a source and a destination

    There are a lot of cases to be handled

    Arguments:
        root:- the root of the AST being analyzed
            stored as (2-tuple) with (root node, array of children )
    """
    

    names = []
    #Set the depth of the root node
    set_depth(root, 0)
    #Stack of nodes to visit
    stack = [root]
    
    #stack of scopes with the highest scope being
    #the smallest. Stored as a [ (scoping_node, scope_depth) ]
    #if the node.depth exceeds scope depth, pop the element
    scopes = [] 

    while len(stack):
        node, children = stack.pop()
        ntype = node_type(node) 

        #remove any stale scopes
        while len(scopes):
            #check `depth` of closest scope    
            if node.depth <= scopes[-1].depth:
                scopes.pop()
            else:
                break
        
        if ntype in scoping_nodes:
            scopes.append(node)

        if ntype == "Name":
            handle_name(node, children, scopes)
        
        elif ntype == "Assign":
            pass

        elif ntype == "Attribute":
            #TODO: attribute chains can be arbitrarily long
            dep_dest = "{}.{}".format(node.value.id, node.attr)
            print "{} => {}".format(scopes_to_str(scopes), dep_dest)
            
            #Don't add children
            continue
            

        #Add children to stack
        #This musn't always be performed
        for child in children[::-1]:
            set_depth(child, node.depth + 1)
            stack.append(child)


    #print names

#TODO: Inner dependencies, i.e generalize check_dependency so as not to only check top level objs
#TODO: Name store vs name load, i.e. scoping
#TODO: Extending to other modules in same package and other packages
#TODO: from `module name` import * 
#TODO: show dependency destination path

def analyze(module_path):
    """
    Analyze dependencies starting at `module_path`
    """
    #view the module as a AST node object
    module = get_module(module_path) 

    nodes = []
    NodeVisitor().visit(module, nodes)
    
    #Modify main module node to give it a name attr
    if not hasattr(nodes[0][0], "name"):
        nodes[0][0].name = name_from_path(module_path)

    #symbolic_pretty_print(nodes)
    pretty_print(nodes)

    create_symbol_table(nodes[0])
    #find_dependencies(nodes[0])


if __name__ == '__main__':
    if len(sys.argv) == 1 or not os.path.isfile(sys.argv[1]):
        print "Usage: python analyze.py <<path to starting module>>"
    else:
        analyze(sys.argv[1])


