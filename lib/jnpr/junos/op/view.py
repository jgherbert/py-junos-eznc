import warnings
from contextlib import contextmanager
from copy import deepcopy
from lxml import etree

from .rsmfields import RunstatMakerViewFields

class RunstatView(object):
  """
  RunstatView is the base-class that makes extracting values from XML 
  data appear as objects with attributes.
  """

  NAME_XPATH = 'name'
  FIELDS = {}
  GROUPS = None

  ### -------------------------------------------------------------------------
  ### CONSTRUCTOR
  ### -------------------------------------------------------------------------

  def __init__(self, table, view_xml):
    """
    :table:
      instance of the RunstatTable

    :view_xml:
      this should be an lxml etree Elemenet object.  This 
      constructor also accepts a list with a single item/XML
    """
    # if as_xml is passed as a list, make sure it only has
    # a single item, common response from an xpath search
    if isinstance(view_xml,list):
      if 1 == len(view_xml):
        view_xml = view_xml[0]
      else:
        raise ValueError("constructor only accepts a single item")

    # now ensure that the thing provided is an lxml etree Element
    if not isinstance(view_xml,etree._Element):
      raise ValueError("constructor only accecpts lxml.etree._Element")  

    self._table = table
    self.NAME_XPATH = table.NAME_XPATH
    self._init_xml( view_xml )

  def _init_xml(self, given_xml):
    self._xml = given_xml
    if self.GROUPS is not None:
      self._groups = {}
      for xg_name,xg_xpath in self.GROUPS.items():
        xg_xml = self._xml.xpath(xg_xpath)
        if not len(xg_xml):  # @@@ this is technically an error; need to trap it
          continue
        self._groups[xg_name] = xg_xml[0]

  ### -------------------------------------------------------------------------
  ### PROPERTIES
  ### -------------------------------------------------------------------------

  @property 
  def T(self):
    """ return the Table instance for the View """
    return self._table

  @property
  def D(self):
    """ return the Device instance for this View """
    return self.T.D 
    
  @property 
  def name(self):
    """ return the name of view item """
    if self.NAME_XPATH is None: return self._table.D.hostname
    if isinstance(self.NAME_XPATH,str):
      # simple key
      return self._xml.findtext(self.NAME_XPATH).strip()
    else:
      # composite key
      return tuple([self.xml.findtext(i).strip() for i in self.NAME_XPATH])

  # ALIAS key <=> name
  key = name

  @property
  def xml(self):
    """ returns the XML associated to the item """
    return self._xml
   
  ### -------------------------------------------------------------------------
  ### METHODS
  ### -------------------------------------------------------------------------

  def keys(self):
    """ list of view keys, i.e. field names """
    return self.FIELDS.keys()

  def values(self):
    """ list of view values """
    return [getattr(self,field) for field in self.keys()]

  def items(self):
    """ list of tuple(key,value) """
    return zip(self.keys(), self.values())

  def _updater_instance(self, more):
    """ called from extend """
    if hasattr(more,'fields'):
      self.FIELDS = deepcopy(self.__class__.FIELDS)
      self.FIELDS.update(more.fields.end)

    if hasattr(more,'groups'):
      self.GROUPS = deepcopy(self.__class__.GROUPS)
      self.GROUPS.update(more.groups)

  def _updater_class(self,more):
    """ called from extend """
    if hasattr(more,'fields'):
      self.FIELDS.update(more.fields.end)

    if hasattr(more,'groups'):
      self.GROUPS.update(more.groups)

  @contextmanager
  def updater(self, fields=True, groups=False, all=True, **kvargs):
    """ 
    provide the ability for subclassing objects to extend the
    definitions of the fields.  this is implemented as a 
    context manager with the form called from the subclass 
    constructor:

      with self.extend() as more:
        more.fields = <dict>
        more.groups = <dict>   # optional
    """
    # -------------------------------------------------------------------------    
    # create a new object class so we can attach stuff to it arbitrarily.  
    # then pass that object to the caller, yo!
    # -------------------------------------------------------------------------    

    more = type('RunstatViewMore',(object,),{})()
    if fields is True:
      more.fields = RunstatMakerViewFields()

    # -------------------------------------------------------------------------
    # callback through context manager
    # -------------------------------------------------------------------------

    yield more
    updater = self._updater_class if all is True else self._updater_instance
    updater(more)

  def asview(self, view_cls ):
    """ create a new View object for this item """
    return view_cls(self._table, self._xml)
    
  def refresh(self):
    """ 
    ~~~ EXPERIMENTAL ~~~
    refresh the data from the Junos device.  this only works if the table
    provides an "args_key", does not update the original table, just this
    specific view/item
    """
    warnings.warn("Experimental method: refresh")
    
    if self._table.can_refresh is not True:
      raise RuntimeError("table does not support this feature")

    # create a new table instance that gets only the specific named
    # value of this view

    tbl_xml = self._table._rpc_get(self.name)
    new_xml = tbl_xml.xpath(self._table.ITER_XPATH)[0]
    self._init_xml(new_xml)
    return self

  ### -------------------------------------------------------------------------
  ### OVERLOADS
  ### -------------------------------------------------------------------------

  def __repr__(self):
    """ returns the name of the View with the associate item name """
    return "%s:%s" % (self.__class__.__name__, self.name)

  def __getattr__(self,name):
    """ 
    returns a view item value, called as :obj.name:
    """
    item = self.FIELDS.get(name)
    if item is None:
      raise ValueError("Unknown field: '%s'" % name)

    if item.has_key('table'):
      found = item['table'](ncdev=self.D, table_xml=self._xml)
    else:
      astype = item.get('astype',str)
      if item.has_key('group'):
        found = self._groups[item['group']].xpath(item['xpath'])
      else:
        found = self._xml.xpath(item['xpath'])

      if astype is bool:
        # handle the boolean flag case separately
        return bool(len(found))

      if 0 == len(found): 
        # even for the case of numbers, do not set the value.  we 
        # want to detect "does not exist" vs. defaulting to 0
        # -- 2013-nov-19, JLS.
        return None   
      try:
        # added exception handler to catch malformed xpath expressesion
        # -- 2013-nov-19, JLS.
        as_str = found[0] if isinstance(found[0],str) else found[0].text
        found = astype(as_str.strip())
      except:
        raise RuntimeError("Unable to handle field:'%s'" % name)

    return found

  def __getitem__(self,name):
    """ 
    allow the caller to extract field values using :obj['name']:
    the same way they would do :obj.name:
    """
    return getattr(self,name)




