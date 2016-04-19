import pprint
import ast

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

def scopes_to_str(scopes):
    """
    Converts a scopes' stack to string
    """
    return '.'.join(map(unique_id, scopes))
