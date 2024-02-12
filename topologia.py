#importar librerias
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
#si cambiamos las interfaces a NAT utilizar las dos siguientes libs
from mininet.link import Intf
from mininet.util import dumpNodeConnections

#Crear topologia de prueba
def createTopology():
	#instancia de objeto MIninet que contiene controlador
	net = Mininet(controller=None)
	
	#agregar controlador
	info('Agregando Controlador\n')
	net.addController('c0', controller=RemoteController, ip='192.168.1.16', port=6633)
	
	#agregar hosts
	info('Agregando Hosts\n')
	#cambiar las IP (si es necesario dependiendo de la interfaces de red (en este caso es interna con /24))
	h1 = net.addHost('h1',ip='192.168.50.91', mac="10:00:00:00:00:00")
	h2 = net.addHost('h2',ip='192.168.50.92', mac="20:00:00:00:00:00")
	h3 = net.addHost('h3',ip='192.168.50.93', mac="30:00:00:00:00:00")
	h4 = net.addHost('h4',ip='192.168.50.94', mac="40:00:00:00:00:00")
	h5 = net.addHost('h5',ip='192.168.50.99', mac="50:00:00:00:00:00")
	#h6 = net.addHost('h6',ip='10.0.0.6')

	#agregar switches 
	info('Agregando Switches\n')
	s1 = net.addSwitch('s1')
	s2 = net.addSwitch('s2')
	s3 = net.addSwitch('s3')		
	s4 = net.addSwitch('s4')
	
	#crear enlaces entre hosts y switches
	info('Creando enlaces\n')
	net.addLink(h1, s2)
	net.addLink(h2, s2)
	net.addLink(h3, s3)
	net.addLink(h4, s3)
	net.addLink(h5, s4)
	#net.addLink(h6, s4)
	
	#variables de switches
	root=s1
	layer1=[s2,s3,s4]

	#crear enlaces entre switches 
	for i,l1 in enumerate (layer1):
		net.addLink(root, l1)
	
	#Inicio
	net.start()
	#acceso linea de comandos
	CLI(net)
	#Finaliza
	net.stop()

#Detalle de la red
setLogLevel('info') 
#ejecutar
createTopology()
