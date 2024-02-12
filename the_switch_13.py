import array
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, arp, ipv4, tcp, udp



#clase Switch OF 1.3
class TheSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    #constructor
    def __init__(self, *args, **kwargs):
        super(TheSwitch13, self).__init__(*args, **kwargs) #inicializa configuraciones en clase principal
        self.mac_to_port = {} #registrar MACs x puerto del switch (handshake L2)
    
    #negociacion para que se reciban mensajes de los switches existentes en la topologia
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        #enviar mensaje de solicitud de caracteristicas
        self.add_flow(datapath, 0, match, actions)

    #crear tabla de flujo
    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id, 
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            #OFPFF_SEND_FLOW_REM notifica por evento que el flujo a sido eliminado una vez que supere el hard_timeout
            mod = parser.OFPFlowMod(command= ofproto.OFPFC_ADD, datapath=datapath, hard_timeout = 20,
                                    priority=priority, flags=ofproto.OFPFF_SEND_FLOW_REM, match=match, instructions=inst) 
        datapath.send_msg(mod)
    
    #crear/modificar datos(packets in)
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        #mensaje del evento
        msg = ev.msg
        #obtener el nro de sw 
        datapath = msg.datapath
        #obtener version protocolo of
        ofproto = datapath.ofproto
        #descomponer/analizar caracteristicas/datos del sw
        parser = datapath.ofproto_parser
        #obtener puerto entrante que coincide con el mensaje de packet in
        in_port = msg.match['in_port']

        #campos para MATCH
        src_ip = None
        dst_ip = None
        protocolo = None
        src_port = None
        dst_port = None

        #obtener paquete entrante (el host envia un paquete al sw, el sw lo recupera)
        pkt = packet.Packet(array.array("B", msg.data))
        #print(pkt)
        eth = pkt[0]
        dst_mac = eth.dst#destino
        src_mac = eth.src#origen

        #establecer identificador de origen datos (sw)
        dpid = format(datapath.id, "d").zfill(16)
        #indicar un mapeo de MACs x puertos segun el id del datapath
        self.mac_to_port.setdefault(dpid, {})
        #self.logger.info("packet in %s %s %s %s", dpid, src_mac, dst_mac, in_port)
        #self.logger.info("packet in %s %s[%s] <-> %s[%s] Port:%s, Proto:%s", dpid, src_mac, src_ip, dst_mac, dst_ip, in_port, protocolo)

        # learn a mac address to avoid FLOOD next time. {clave: {valor(clave):valor}}
        self.mac_to_port[dpid][src_mac] = in_port# establecer puerto de entrada x srcmac segun datapathID(sw)

        #si la mac destino existe en un puerto del sw
        if dst_mac in self.mac_to_port[dpid]:
            #obtener puerto de salida(se encuentra creado si anteriormente se ha creado un evento PacketIn)
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            #realizar multicast. All physical ports except input port and those disabled by STP.
            out_port = ofproto.OFPP_FLOOD # =0xfffffffb
        #preparar la actividad segun el valor de outport
        actions = [parser.OFPActionOutput(out_port)]

        #analizar tipos de tramas ethernet

        #si es arp
        if eth.ethertype == 2054:
            arp_ = pkt.get_protocol(arp.arp)
            protocolo = arp_.proto
            dst_ip = arp_.dst_ip
            dst_mac = arp_.dst_mac  
            src_ip = arp_.src_ip
            src_mac = arp_.src_mac 

        #si es ipv4
        if eth.ethertype == 2048:
            #extraer datos de protocolos
            ip = pkt.get_protocol(ipv4.ipv4)
            protocolo = ip.proto
            src_ip = ip.src
            dst_ip = ip.dst

            # verificar si el paquete es icmp
            if protocolo == 1:
                pass

            # si el contenido es TCP
            if protocolo == 6:
                tcp_ = pkt.get_protocol(tcp.tcp)
                src_port = tcp_.src_port
                dst_port = tcp_.dst_port

            # si el contenido es UDP
            if protocolo == 17:
                udp_ = pkt.get_protocol(udp.udp)
                src_port = udp_.src_port
                dst_port = udp_.dst_port


        # install a flow to avoid packet_in next time

        #si el puerto de salida es diferente a un puerto que esta haciendo multicast
        if out_port != ofproto.OFPP_FLOOD:
            #enviar campos de coincidencia/soporte opcionales para integrar al flujo
            #para trama tipo ARP
            if eth.ethertype == 2054:
                match = parser.OFPMatch(in_port = in_port, eth_dst = dst_mac, eth_src = src_mac, eth_type = eth.ethertype, ip_proto=protocolo, ipv4_src = src_ip, ipv4_dst = dst_ip)
            #para trama tipo IPv4  
            elif eth.ethertype == 2048:
                # si es ICMP
                if protocolo == 1:
                    match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac, eth_src=src_mac, eth_type=eth.ethertype, ip_proto=protocolo, ipv4_src = src_ip, ipv4_dst = dst_ip)
                #si es TCP
                if protocolo == 6:
                    match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac, eth_src=src_mac, eth_type=eth.ethertype, ip_proto=protocolo, ipv4_src = src_ip, ipv4_dst = dst_ip, 
                                            tcp_src = src_port, tcp_dst = dst_port)
                #si es UDP 
                if protocolo == 17:
                    match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac, eth_src=src_mac, eth_type=eth.ethertype, ip_proto=protocolo, ipv4_src = src_ip, ipv4_dst = dst_ip, 
                                            udp_src = src_port, udp_dst = dst_port)
            #sea el caso de IPv6 u otros protocolos
            else:
                match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac, eth_src=src_mac)

            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                #si se tiene un buffer id configurado se agrega ese campo adicional a la tabla de flujo
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                #agregamos a la tabla de flujo
                self.add_flow(datapath, 1, match, actions)
        
        data = None
        #el buffer id es igual a 0xffffffff(puede indicar 1. que todos los bufferes estan ocupados 2.señal de que el procesamiento del paquete llega a su final)
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            #se recupera el contenido del paquete
            data = msg.data
        #una vez agregados los datos a la tabla de flujos
        #indica la salida del paquete
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        #se notifica al swith de que debe generar un PacketOut
        datapath.send_msg(out)

    #evento de eliminacion de flujos
    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto

        if msg.reason == ofp.OFPRR_IDLE_TIMEOUT:
            reason = 'IDLE TIMEOUT'
        elif msg.reason == ofp.OFPRR_HARD_TIMEOUT:
            reason = 'HARD TIMEOUT'
        elif msg.reason == ofp.OFPRR_DELETE:
            reason = 'DELETE'
        elif msg.reason == ofp.OFPRR_GROUP_DELETE:
            reason = 'GROUP DELETE'
        else:
            reason = 'unknown'

        self.logger.debug('OFPFlowRemoved received: '
                        'cookie=%d priority=%d reason=%s table_id=%d '
                        'duration_sec=%d duration_nsec=%d '
                        'idle_timeout=%d hard_timeout=%d '
                        'packet_count=%d byte_count=%d match.fields=%s',
                        msg.cookie, msg.priority, reason, msg.table_id,
                        msg.duration_sec, msg.duration_nsec,
                        msg.idle_timeout, msg.hard_timeout,
                        msg.packet_count, msg.byte_count, msg.match)