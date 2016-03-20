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

import sys
import pdb

def get_node(filepath):
    """
    Returns a AST node object corresponding to argument file
    
    Arguments:- filepath
        name of file to converted

    Return: AST node object
    """
    f = open(filepath, "r")
    lines = "".join(f.readlines())
    f.close()
    
    node = ast.parse(lines)
    return node

def pretty_print(self_map):
    pprint.pprint(self_map)

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
    The methods visit, generic_visit copied from ast.py and
    lightly modified. 
    
    The attributes i.e. name, arg, decorators etc. are 
    properties of the node obj. The attributes vary depending on
    the specific node obj, i.e. a function has an arg, whereas a 
    class does not.
    
    """ 
    def visit(self, node, node_map):
        """Visit a node."""
        node_type = node.__class__.__name__
        method = 'visit_' + node_type 
        visitor = getattr(self, method, self.generic_visit)
        
        """
        If visitor method does not exist, calls generic visit
        i.e. the following statement is either visit_FOO(...) 
        or generic_visit(...)
        """
        return visitor(node, node_map)

    def generic_visit(self, node, parent_map):
        """Called if no explicit visitor function exists for a node.
        @Args
            node (AST Node)- the AST node to visit
            node_map (dict)- this node's map, contains descendents
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


def get_top_level_objects(tree):
    """
    Returns direct children of module object
    root is the module object
    """
    root, children = tree
    return [child[0] for child in children if node_type(child[0]) in consts.AST_NODE_TYPES2]
    
def find_names(tree):
    """
    Returns lists of paths to `Name` nodes
    """
    root, children = tree
    
    #list of name nodes
    names = []

    if node_type(root) == "Name":
        names.append([root])
    
    for child in children:
        #Names in descendent tree
        desc_names = find_names(child)
        for dn in desc_names: 
            #prepend current node
            dn.insert(0, root)
            names.append(dn)

    return names

def get_dependee_path(path):
    """
    Get dependee path with all relevant nodes
    """
    return [node for node in path[:-1]
        if node_type(node) in consts.AST_NODE_TYPES2]
            


def check_dependency(top_objs, path):
    """
    Checks if path has dependency to obj in 
    top_objs
    
    This may not be correct since unique_id does not return a unique id
    Typically it resolves to an attribute that is unique enough and 
    descriptive; however this is problematic if there are name collisions
    """
    for obj in top_objs:
        ntype = node_type(obj)
        #If comparing with top level obj of type Import
        if ntype == "Import" and node_type(path[-2]) == "Attribute": 
            attr_node = path[-2]
            if unique_id(obj) == unique_id(attr_node):
                #There is a dependency found
                #print this `depends on` this
                dependee = get_dependee_path(path)
                pretty_path = ".".join(map(unique_id, dependee))
                print "{} => {}.{}".format(pretty_path, attr_node.value.id, attr_node.attr)
                return (pretty_path, "{}.{}".format(attr_node.value.id, attr_node.attr))
        
        elif ntype == "ImportFrom":
            for name in obj.names:
                if unique_id(path[-1]) == name.name:
                    dependee = get_dependee_path(path)
                    pretty_path = ".".join(map(unique_id, dependee))
                    print "{} => {}.{}".format(pretty_path, obj.module, name.name)
                    return (pretty_path, "{}.{}".format(obj.module, name.name ))
         
        else:
            if unique_id(obj) == unique_id(path[-1]):
                dependee = get_dependee_path(path)
                pretty_path = ".".join(map(unique_id, dependee))
                #There is a dependency found
                print "{} => {}".format(pretty_path, unique_id(path[-1]))
                return (pretty_path, unique_id(path[-1]))
        
    return 

def name_from_path(path):
    """Returns name of a module given its path; strips '.py' """
    return path[0:-3]

def to_json(dependencies, data_path="DependencyWheel/data/data.json"):
    """
    Create a dependency matrix

    JSON should be of format: 
    {
        "packageNames": ["Main", "A", "B"],
        "matrix": [[0, 1, 1],
                   [0, 0, 1],  
                   [0, 0, 0]]
    }

    """

    nodes = []
    for dep in dependencies:
        nodes.append(dep[0])
        nodes.append(dep[1])
    
    nodes = list(Set(nodes))
    ncount = len(nodes)
    
    
    matrix = []
    for node in nodes:
        matrix.append( [0] * ncount )
        for dep in dependencies:
            if dep[0] == node:
                matrix[-1][nodes.index(dep[1])] = 1
    
    #print nodes
    #print matrix

    data = {"packageNames": nodes, "matrix": matrix}
    with open(data_path, 'w') as outfile:
        json.dump(data, outfile)


#TODO: Inner dependencies, i.e generalize check_dependency so as not to only check top level objs
#TODO: Name store vs name load, i.e. scoping
#TODO: Extending to other modules in same package and other packages
#TODO: from `module name` import * 
#TODO: show dependency destination path

def analyze(module_path):
    """
    Analyze dependencies starting at `module_path`
    """
    module = get_node(module_path) 

    nodes = []
    NodeVisitor().visit(module, nodes)

    #Modify main module node to give it a name attr
    if not hasattr(nodes[0][0], "name"):
        nodes[0][0].name = name_from_path(module_path)

    pretty_print(nodes)
    print "" 

    top_objs = get_top_level_objects(nodes[0])
    #print top_objs
    #pdb.set_trace()
    print ""
    paths = find_names(nodes[0])
    #for n in paths: print n 
     
    dependencies = [] 
    for path in paths:
        match = check_dependency(top_objs, path)
        if match: 
            dependencies.append( match )
    
    print dependencies 
    to_json(dependencies)
    

if __name__ == '__main__':
    if len(sys.argv) == 1 or os.path.isfile(sys.argv[1]):
        print "Usage: python analyze.py <<path to starting module>>"
    else:
        analyze(sys.argv[1])


