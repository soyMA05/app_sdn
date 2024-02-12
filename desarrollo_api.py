#librerias
from flask import Flask, request, jsonify
import pickle
import numpy as np

#VARIABLES

#modelos
model_mlfg1 = pickle.load(open('p_dt_FG1.pkl','rb'))
model_mlfg2 = pickle.load(open('p_dt_FG2.pkl','rb'))
model_mlfg3 = pickle.load(open('p_dt_FG3.pkl','rb'))
model_mlfg4 = pickle.load(open('p_dt_FG4.pkl','rb'))

# instanciar framework
flask = Flask(__name__)

#METODOS

#ruta de conocimiento (comprobar acceso cuando se configuro la VPN para usar el servidor)
@flask.route('/')
def home():
    return "---Hello!, continue with work of SDN---"


#predice con 9 caracteristicas
@flask.route('/predict',methods=['POST'])
def predict():
    #obtener matriz de caracteriticas
    dur = request.form.get('Dur')
    prototcp = request.form.get('protoTcp')
    protoudp = request.form.get('protoUdp')
    portsys = request.form.get('portSystem')
    portus = request.form.get('portUser')
    portdyn = request.form.get('portDynamic')
    totpkts = request.form.get('TotPkts')
    srcpkts = request.form.get('SrcPkts')
    dstpkts = request.form.get('DstPkts')
    totbytes = request.form.get('TotBytes')
    srcbytes = request.form.get('SrcBytes')
    dstbytes = request.form.get('DstBytes')
    
    #result = {'dur':dur, 'dport':dport, 'proto':proto, 'totpkts':totpkts,'totbytes':totbytes,'load':load}
    #return jsonify(result)

    #transformar las entradas en un vector unico
    input_query = np.array([[dur, prototcp, protoudp, portsys, portus, portdyn, totpkts, srcpkts, dstpkts, totbytes, srcbytes, dstbytes]])
    result = model_mlfg1.predict(input_query)[0] #consultar entradas al modelo
    #enviar respuesta
    return jsonify({'input_query': str(input_query),
        'Label':str(result)})

#predice con 12 caracteristicas
@flask.route('/predictfg2',methods=['POST'])
def predict():
    #obtener matriz de caracteriticas
    dur = request.form.get('Dur')
    prototcp = request.form.get('protoTcp')
    protoudp = request.form.get('protoUdp')
    portsys = request.form.get('portSystem')
    portus = request.form.get('portUser')
    portdyn = request.form.get('portDynamic')
    totpkts = request.form.get('TotPkts')
    srcpkts = request.form.get('SrcPkts')
    dstpkts = request.form.get('DstPkts')
    totbytes = request.form.get('TotBytes')
    srcbytes = request.form.get('SrcBytes')
    dstbytes = request.form.get('DstBytes')
    rate = request.form.get('Rate')
    srcrate = request.form.get('SrcRate')
    dstrate = request.form.get('DstRate')
    #transformar las entradas en un vector unico
    input_query = np.array([[dur, prototcp, protoudp, portsys, portus, portdyn, totpkts, srcpkts, dstpkts, totbytes, srcbytes, dstbytes, rate, srcrate, dstrate]])
    result = model_mlfg2.predict(input_query)[0] #consultar entradas al modelo
    #enviar respuesta
    return jsonify({'input_query': str(input_query),
        'Label':str(result)})

"""
Realizar mas metodos con la misma estructura para las demas caracteristicas
"""

#ejecutar todos los metodos POSTs para que las diferentes solicitudes trabajen con diferentes grupos de caracteristicas
if __name__=='__main__':
    flask.run(debug=True)




