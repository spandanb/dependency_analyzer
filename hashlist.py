
class hashlist(dict):
    """
    Implements a hashmap like data structure, where keys 
    are mapped to a list of sorted items. Alternatively, a
    priority queue could be used to order the values, albeit
    with higher memory usage.

    TODO: __delitem__
    """
    def __init__(self, *args, **kw):
        super(hashlist,self).__init__(*args, **kw)

    def __setitem__(self, key, value):
        if not key in self: 
            #new entry, create a mapping from key to 
            #list of value
            super(hashlist,self).__setitem__(key, [value])
        else:

            for i, val in enumerate(self[key]):
                if val == value: 
                    #Don't insert duplicates
                    break 
                elif val > value: 
                    #should be okay to modify, since we will break
                    self[key].insert(i, value)
                    break
            else:
                #Append at tail
                self[key].append(value)
                

if __name__ == "__main__":
    hl = hashlist()
    hl['a'] = 32
    hl['a'] = 11
    hl['b'] = 2
    hl['a'] = 39

    print hl

