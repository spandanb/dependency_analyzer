import pprint
import ast

def name_from_path(filepath):
    """
    Returns the name of the module
    given path to module
    """
    #get filename
    filename = filepath.split("/")[-1]
    #remove extension, only works for .py files
    return filename[0:-3]

def get_module(filepath):
    """
    Returns a AST node object corresponding to argument file.
    In addition sets `lineno` and `lineno_end` for starting and 
    ending line number (inclusive).
    
    Arguments:- filepath
        name of file to converted

    Return: AST node object
    """
    with open(filepath, "r") as fileptr:
        src = fileptr.read()
    node = ast.parse(src)

    #set a name prop if does not exist
    if not hasattr(node, "name"):
        node.name = name_from_path(filepath) 

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

    if ntype == 'Str':
        identifier = node.s
    elif ntype == 'Num':
         identifier = node.n
    #NOTE: Call doesn't always resolve properly
    elif ntype == 'Call' and hasattr(node.func, 'id'): 
         identifier = node.func.id
    elif ntype == 'Attribute':
        identifier = node.value.id
    elif ntype == 'ImportFrom':
        identifier = node.module
    elif ntype == 'Module':
        identifier = node.name
    elif hasattr(node, "name"):
        identifier = node.name
    elif hasattr(node, "id"):
        identifier = node.id
    elif isinstance(node, str):
        identifier = node
    else:
        #identifier = id(node)    
        identifier = str(node)    
    return str(identifier)

def nodes_to_str(nodes):
    """
    Converts a list of nodes to string 
    """
    return '.'.join(map(unique_id, nodes))
