"""
This module contains the functions and classes that analyze
the code or directly help in the analysis.
"""
import ast
from sets import Set
import json
import os.path
import consts
from datastructures import STable, DTable, Stack
import sys
import pdb
from collections import namedtuple
import importlib

from utils import get_module, pretty_print, unique_id, node_type, scopes_to_str


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



###############################################################
#####################      TODO     ###########################
#1)
#Use a class: There is too much state that needs to be managed

#2)
# stack.pop() takes the last item
#but items are added in the opposite order

#3)
#Handle function parameters

#4)
#When doing import foo as bar
#you should store the name foo
#if you intent to analyze dependencies
#across modules
#Need a generalized symbol table that stores both names.
#i.e. a symbol table at the project level
###############################################################

"""
These setters and getter exists
in case the data structure of node is changed
"""
def set_depth(node, depth):
    """Set the depth of an AST node
    """
    setattr(node[0], "depth", depth)

def set_lineno(node, children):
    """
    Sets lineno and lineno_end of all children of node.
    Assigns lineno_end of ith child as the
    the lineno of i+1 th child. 
    
    Some AST nodes don't have a `lineno` property;
    in these cases sets it based on the following algorithm.
    """
    for i, child in enumerate(children):
        child = child[0]
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
    The symbol table has to be created in its entirety 
    first, since entities (e.g. functions, classes) can be 
    referenced before being defined.

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
    #Initialize the stack, with the AST root
    stack = Stack(root)

    #the symbol table maps the name to the scope.
    #Any node can belong to multiple scopes, therefore this
    #is a list of scope
    symbol_table = STable()
    
    #this represents objects imported from
    #other modules
    other_modules = {}

    for node, children, ntype in stack:

        if ntype == "Import":
            #Import object has names prop which
            #is an array of names
            for name in node.names:
                #name can be the name or an alias   
                name_val = name.asname or name.name
                #insert in symbol_table                
                symbol_table[name_val] = ()

        elif ntype == "ImportFrom":
            if node.names[0].name == '*':
                try:
                    imp_mod = importlib.import_module(node.module)
                    #Add all names in imported module, except those
                    #starting with '_'
                    for name in dir(imp_mod):
                        if name[0] != '_':
                            symbol_table[name] = stack_top(scopes)

                except ImportError:
                    print "Error: local system does not have {}. Skipping!".format(node.module)
                    pass
            else:
                #TODO: store node.module
                for name in node.names:
                    #TODO: store name.name even if name.asname defined    
                    name_val = name.asname or name.name
                    symbol_table[name_val] = stack.get_scopes(src_module=node.module)

        elif ntype == "ClassDef" or ntype == "FunctionDef":   
            symbol_table[node.name] = stack.get_scopes()
        
        #NOTE: if a name is being loaded then it already exists and doesn't need
        #to be added to symbol_table
        elif ntype == "Name" and not is_load(children) and not has_global(stack.scope_tail(), node.id): 
            symbol_table[node.id] = stack.get_scopes()

        elif ntype == "arguments":
            if node.vararg: 
                symbol_table[node.vararg] = stack.get_scopes()
            if node.kwarg:
                symbol_table[node.kwarg] = stack.get_scopes()

        elif ntype == "Global":
            #add a list global vars on node on the top of  
            #the stack
            #nonlocal could be handled in similar way
            set_globals(scopes[-1], node.names)

        #set lineno property of children nodes
        set_lineno(node, children)

        for child in children[::-1]:
            #set depth of child
            set_depth(child, node.depth + 1)
            #Add children to stack
            stack.append(child)

        #Add any new scopes
        #Need to do it here since scoping_nodes are defined in their parent scope
        stack.check_and_push_scope()

    print "Symbol table is "
    print symbol_table
    return symbol_table
    

def find_dependencies(root):
    """
    Finds all dependencies in root object based on symbol table. 
    Consider a dependecy as containing a source and a destination.


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

    There are a lot of cases to be handled

    Arguments:
        root:- the root of the AST being analyzed
            stored as (2-tuple) with (root node, array of children )
    """
    
    symbol_table = create_symbol_table(root)

    names = []
    #Set the depth of the root node
    set_depth(root, 0)
    #Stack of nodes to visit
    stack = Stack(root)
    
    #List of (src, dest) of dependencies
    dependency_table = DTable(symbol_table=symbol_table)

    for node, children, ntype in stack:
        
        stack.check_and_push_scope()

        #A Name is being loaded, therefore 
        if ntype == "Name" and is_load(children):
            """
            """
            dependency_table.append( (stack.scopes, node))
        
        elif ntype == "Assign":
            #TODO need to add assignments and then revoke them
            #for child in children:
            #print children
            pass

            
        elif ntype == "Attribute":
            #TODO: attribute chains can be arbitrarily long
            #dep_dest = "{}.{}".format(node.value.id, node.attr)
            #print "{} => {}".format(scopes_to_str(scopes), dep_dest)

            #TODO: Can't just do dependency_table.append( (scopes, node))
            #since the unique_id function won't match the create the dep string like 
            #{node.value.id}.{node.attr}.
            #Either generalize unique_id or something else.
            
            #Don't add children
            continue
            
        set_lineno(node, children)
        #Add children to stack
        #This musn't always be performed
        for child in children[::-1]:
            set_depth(child, node.depth + 1)
            stack.append(child)

    print "dependency table is "
    print dependency_table 

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
    #pretty_print(nodes)

    #create_symbol_table(nodes[0])
    find_dependencies(nodes[0])


if __name__ == '__main__':
    if len(sys.argv) == 1 or not os.path.isfile(sys.argv[1]):
        print "Usage: python analyze.py <<path to starting module>>"
    else:
        analyze(sys.argv[1])


