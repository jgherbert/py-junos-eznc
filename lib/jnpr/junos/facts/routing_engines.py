from string import maketrans
import re as RE

def routing_engines(junos, facts):

  tr = maketrans('-','_')

  re_facts = ['mastership-state','status','model','up-time','last-reboot-reason']
  re_info = junos.rpc.get_route_engine_information()

  master = []
  for re in re_info.xpath('.//route-engine'):
    x_re_name = re.xpath('ancestor::multi-routing-engine-item/re-name')

    if not x_re_name:
      # not a multi-instance routing engine platform, but could
      # have multiple RE slots
      re_name = "RE" 
      x_slot = re.find('slot')
      slot_id = x_slot.text if x_slot is not None else "0"
      re_name = re_name + slot_id
    else:
      # multi-instance routing platform
      m = RE.search('(\d)', x_re_name[0].text)
      re_name = "RE" + m.group(0)   # => RE0 | RE1

    re_fd = {}
    facts[re_name] = re_fd
    for factoid in re_facts:
      x_f = re.find(factoid)
      if x_f is not None:
        re_fd[factoid.translate(tr)] = x_f.text

    if 'mastership_state' in re_fd:
      if facts[re_name]['mastership_state'] == 'master':
        master.append(re_name)

  len_master = len(master)
  if len_master > 1:
    facts['master'] = master
  elif len_master == 1:
    facts['master'] = master[0]
