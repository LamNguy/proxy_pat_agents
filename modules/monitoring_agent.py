import netns
import requests
import iptc

class MonitorAgent:

	__agent__ = None
	logger = None
	def __init__ (self,conn,logger):
		if MonitorAgent.__agent__ is None:
			MonitorAgent.__agent__ = self
			MonitorAgent.logger = logger
		else:
			raise Exception('You are allowed to create only one Agent')

		self.conn = conn

	@staticmethod
        def router_ports_querry( router_id ):
                with netns.NetNS( nsname = router_id):
                        prerouting = iptc.easy.dump_chain('nat','custom-PREROUTING',ipv6=False)
                        postrouting = iptc.easy.dump_chain('nat','custom-POSTROUTING',ipv6=False)
                        server_nat_ports = {}
                        mapping_ports = {}
                        router_nat_ports = []
                        # list vm_port which vm opened (vms)
                        for rule in postrouting:
                                dst = rule['dst'][:-3]
                                if dst in server_nat_ports:
                                        server_nat_ports[dst].append(rule['tcp']['dport'])
                                else:
                                        server_nat_ports[dst] = []
                                        server_nat_ports[dst].append(rule['tcp']['dport'])

                        for rule in prerouting:
                                src = rule['target']['DNAT']['to-destination']
                                dport = rule['tcp']['dport']
                                # the port which router opened (vmy)
                                router_nat_ports.append(dport)
                                # mapping the vm_port_opened with router_port_opened
                                mapping_ports[src] = dport
                        return server_nat_ports, mapping_ports, router_nat_ports

	@staticmethod
	def monitoring ():
		namespaces = MonitorAgent.__agent__.get_routers() 
		for namespace in namespaces:
			# get gateway
			gateway = MonitorAgent.__agent__.conn.network.get_router(namespace).external_gateway_info['external_fixed_ips'][0]['ip_address']
			server_nat_ports, mapping_ports, router_nat_ports = MonitorAgent.__agent__.router_ports_querry(  'qrouter-' +  namespace )

                	if not bool (server_nat_ports): continue 

                	for server_ip,server_ports in server_nat_ports.items():
                        	check = MonitorAgent.__agent__.check_server_life_cycle(server_ip)
                        	if check is False:
					MonitorAgent.logger.info('Detect server with ip {} is deleted, so remove all its pat connection'.format(server_ip))
                                	for port in server_nat_ports[server_ip]:
                                        	mapping = server_ip + ':' + port
                                        	MonitorAgent.__agent__.remove_pat_request(server_ip,namespace,port,gateway)
                        	else:
                                	MonitorAgent.logger.info('VM existed')

	@staticmethod
	def check_server_life_cycle(server_ip):
                ports = MonitorAgent.__agent__.conn.network.ports()
                port = next((i for i in ports if i['fixed_ips'][0]['ip_address'] == server_ip),None)
		check = False if port is None else True
                return check 

	@staticmethod
	def get_namespaces():
		return [ 'qrouter-' + i.id for i in MonitorAgent.__agent__.conn.network.routers() ]

	@staticmethod
        def get_routers():
                return [  i.id for i in MonitorAgent.__agent__.conn.network.routers() ]


	@staticmethod
	def remove_pat_request (server_ip, router_id, remove_server_port, gateway):
		payload = {
                	'server_ip': server_ip,
                        'router_id': 'qrouter-' + router_id,
                        'remove_server_port': remove_server_port,
                        'gateway': gateway 
                }
               
		url = 'http://localhost:3000/pat/remove'

                response = requests.post(url = url, params = payload).json()	
		print(response)

	@staticmethod
	def check_namespace( _ns_ ):
		try:
			MonitorAgent.logger.info('Start check namespace...')
			with netns.NetNS( nsname = _ns_): 

                                nat = iptc.Table(iptc.Table.NAT)
				prerouting_chain = iptc.Chain(iptc.Table(iptc.Table.NAT), "PREROUTING")
                                postrouting_chain = iptc.Chain(iptc.Table(iptc.Table.NAT), "POSTROUTING")
				
				# chech user define chains 
                                if 'custom-PREROUTNG' not in [ i.name for i in nat.chains ]:
					MonitorAgent.logger.info('Check custom-prerouting on router {} False'.format(__ns__))
                                       	nat.create_chain('custom-PREROUTING')
				else:
					MonitorAgent.logger.info('Check custom-prerouting on router {} True'.format(__ns__))

                                if 'custom-POSTROUTING' not in [i.name for i in nat.chains]:
					MonitorAgent.logger.info('Check custom-postrouting on router {} False'.format(__ns__))
                                       	nat.create_chain('custom-POSTROUTING')
				else:
					MonitorAgent.logger.info('Check custom-postrouting on router {} True'.format(__ns__))

                                if 'custom-PREROUTING' not in [ i.target.name for i in prerouting_chain.rules ]:
					MonitorAgent.logger.info('Check custom-prerouting reference on router {} False'.format(__ns__))
                                       	rule_goto = { 'target': 'custom-PREROUTING'}
                                       	iptc.easy.insert_rule('nat','PREROUTING',rule_goto)
				else:
					MonitorAgent.logger.info('Check custom-prerouting reference on router {} True'.format(__ns__))

                                if 'custom-POSTROUTING' not in [ i.target.name for i in postrouting_chain.rules ]:
					MonitorAgent.logger.info('Check custom-postrouting reference on router {} False'.format(__ns__))
                                        rule_goto = { 'target': 'custom-POSTROUTING'}
                                        iptc.easy.insert_rule('nat','POSTROUTING',rule_goto)
				else:
					MonitorAgent.logger.info('Check custom-postrouting reference on router {} True'.format(__ns__))
                except Exception as e:
                	MonitorAgent.logger.error(e) 
		finally:
			nat.close()
                	nat._cache.clear()
