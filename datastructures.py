from utils import unique_id, scopes_to_str

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
                dest = "{}.{}".format(scope[2], unique_id(dest))
                src = scopes_to_str(src)
                super(DTable, self).append((src, dest))
                break
        


if __name__ == "__main__":
    pass
