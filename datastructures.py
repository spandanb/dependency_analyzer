from utils import unique_id, scopes_to_str, node_type
from collections import namedtuple

class STable(dict):
    """
    Implements a hashmap like data structure, where keys 
    are mapped to a list of sorted items. Alternatively, a
    priority queue could be used to order the values, albeit
    with higher memory usage.

    This is custom datastructure intended to be used as a symbol table on
    account of things like comparing only first 2 entries of 
    val

    TODO: __delitem__
    """
    def __init__(self, *args, **kw):
        super(STable, self).__init__(*args, **kw)

    def __setitem__(self, key, value):
        if not key in self: 
            #new entry, create a mapping from key to 
            #list of value
            super(STable, self).__setitem__(key, [value])
        else:
            #val
            for i, val in enumerate(self[key]):
                #The comparison is only based on the
                #first 2 elements, i.e. lineno and lineno_end
                if val[:2] == value[:2]: 
                    #Don't insert duplicates
                    break 
                elif val[:2] > value[:2]: 
                    #should be okay to modify, since we will break
                    self[key].insert(i, value)
                    break
            else:
                #Append at tail
                self[key].append(value)
                
class DTable(list):
    """
    A list like data structure. 

    Specifically intended to store dependencies
    """
    def __init__(self, symbol_table=None):
        super(DTable, self).__init__()
        self.symbol_table = symbol_table

    def append(self, value):
        """
        Adds a value to the datastructure.

        The value is a dependency pair, i.e. (src, dest). 
        e.g. `y = x`, here value would be ('y', 'x'), since y is the 
        src of the dependency (here src should be interpreted as the progenitor, 
        since without y, x would just be and there would be no dependency.

        We know `y`'s context, since this method is called from y`s context.
        But what about x. Here, we use the symbol table to resolve `x`'s context. 
        """
        #value is a 2-tuple of dependency src (scopes) and dest (node)
        src, dest = value
        
        #find first entry in symbol_table that
        #(inclusively) contains node.lineno
        for i, scope in enumerate(self.symbol_table[unique_id(dest)]):
            #TODO: make sure the following makes sense    
            if dest.lineno >= scope[0] and dest.lineno <= scope[1]:
                #check if type is a module import
                if scope.src_module:
                    dest = "{}.{}".format(scope.src_module, unique_id(dest))
                else:
                    dest = "{}.{}".format(scope.scopes, unique_id(dest))
                src = scopes_to_str(src)
                super(DTable, self).append((src, dest))
                break
        

Scopes = namedtuple('scopes', ['lineno', 'lineno_end', 'scopes', 'src_module' ])

#These are the node types that create a scope
#global and nonlocal vars need to tracked separately
scoping_nodes = ["Module", "ClassDef", "FunctionDef"]

class Stack(object):
    """
    A class for representing a stack as used in create_symbol_table
    and find_dependencies.
    """
    def __init__(self, root):
        #the stack itself
        self.stack = [root]

        #stack representing the geneology of scopes that apply to the
        #current context with the highest scope being
        #the smallest. Individual scopes are defined as the triple (lineno, lineno_end, scope_string).
        #if the node.depth exceeds scope depth, pop the element
        self.scopes = []

    def __iter__(self):
        return self

    def next(self):
        if not self.stack:
            raise StopIteration
        else:
            self.node, self.children = self.stack.pop()
            self.ntype = node_type(self.node)
    
            #remove any stale scopes
            while self.scopes:
                #check `depth` of closest scope    
                if self.node.depth <= self.scopes[-1].depth:
                    self.scopes.pop()
                else:
                    break
            
            return self.node, self.children, self.ntype

    def append(self, child):
        "Append a node onto the stack"
        self.stack.append(child)

    def get_scopes(self, src_module=None):
        """
        Returns a 4-tuple representing the top of the stack
        consists of (lineno, lineno_end, str of scopes, src module)
        src_module only applies when modules are imported and properties 
        must be correctly resolved.
        """
        return Scopes(lineno     = self.scopes[-1].lineno, 
                      lineno_end = self.scopes[-1].lineno_end, 
                      scopes     = scopes_to_str(self.scopes),
                      src_module = src_module)

    def scope_tail(self):
        """
        Returns the tail of the scopes
        """
        return self.scopes[-1]

    def check_and_push_scope(self):
        """
        pushes node on `scopes` stack if it is a
        scoping node
        """
        if self.ntype in scoping_nodes:
            self.scopes.append(self.node)
         

if __name__ == "__main__":
    pass
