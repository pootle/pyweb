import subprocess
"""
A little bit of Python that returns info about available network interaces and key IP4
info for each.
Includes a simple utility function that returns just a list of (non loopback) IP4 adresses
"""
def netinf():
    """
    parses the output from ifconfig' and returns key info.
    
    returns a dict with keys being the name of the interface and each value being a list of dicts:
    
        each dict with possible entries:
            'peer'      : ip4 host address (if there is one)
            'netmask'   : mask for this subnet
            'broadcast' : broadcast address
            'mac_addr'  : mac address
            plus any other parts found on the inet line as key / value pairs
    """
    co = subprocess.run(['/sbin/ifconfig'], capture_output=True, text=True)
    ifaces={}
    alines=co.stdout.split('\n')
    def lineget():
        if alines:
            return alines.pop(0)+'\n'
        else:
            return ''
    aline=lineget()
    while aline:
        if aline[0] in (' ','\n'):
            print('unexpected line:', aline)
            aline=lineget()
        else:
            iname, rest = aline.split(':', maxsplit=1)
            ifaceinfo={}
            ifaces[iname] = ifaceinfo
            aline=lineget()
            while aline and aline[0] == ' ':
                lparts = [p.strip() for p in aline.strip().split(' ') if not p.strip() == '']
                if lparts[0]=='inet':
                    _sectadd(ifaceinfo,'IP4',_ip4parse(lparts))
                elif lparts[0]=='inet6':
                    pass
                elif lparts[0] == 'ether':
                    _sectadd(ifaceinfo, 'mac_addr', lparts[1])
                elif lparts[0] in ('loop', 'RX', 'TX'):
                    pass
                else:
                    print('???', lparts)
                    print(lparts[0])
                aline=lineget()
            if len(aline) == 0:
                pass # loop will exit - we're done
            else:
                while aline and aline[0]== '\n':
                    aline=lineget() # skip to next interface
    alines=co.stderr.split('\n')
    for aline in alines:
        if len(aline) > 1:
            print('-x->', aline)
    return ifaces

def _sectadd(dd, key, val):
    if not key in dd:
        dd[key]=[val]
    else:
        dd[key].append(val)

def _ip4parse(lparts):
    ip4inf = {'peer': lparts[1]}
    for x in range(2, len(lparts)-1, 2):
        ip4inf[lparts[x]] = lparts[x+1]
    return ip4inf

def allIP4():
    """
    returns a list of all the IP4 addresses available (excluding loopback)
    """
    return  [e['peer'] for x in netinf().values() if 'IP4' in x for e in x['IP4'] if 'peer' in e and e['peer'] != '127.0.0.1']

def showserverIP(port):
    ips = allIP4()
    if len(ips)==0:
        smsg='starting webserver on internal IP only (no external IP addresses found), port %d' % port
    elif len(ips)==1:
        smsg='Starting webserver on %s:%d' % (ips[0], port)
    else:
        smsg='Starting webserver on multiple ip addresses (%s), port:%d' % (str(ips), port)
    print(smsg)
