################################
# Agente de Analisis Economico #
# Agente - Version Streamlit   #
################################

# Importacion para el ambiente
from dotenv import load_dotenv

# Importacion para el LLM
from groq import Groq

# Importacion para el manejo de sistema
import os

# Importacion para el uso de formato JSON
import json

# Importacion para el manejo de fechas y zonas horarias
from datetime import datetime
from zoneinfo import ZoneInfo

# Importacion para la interfaz visual
import streamlit as st

# Importacion para el manejo memoria y herramientas#
from basic_memory import BasicMemory
from supabase_memory import SupabaseMemory
from advanced_tools import AdvancedTools


# =========================
# CONFIGURACION ORIGINAL
# =========================

# La configuracion de la pagina debe ir antes que cualquier otra
# instruccion de Streamlit, por eso se coloca al inicio.
st.set_page_config(
    page_title="EconoBot",
    page_icon="📊",
    layout="centered"
)

# Cargar variables de entorno #
load_dotenv()

# Obtener la clave de API.
# En la computadora local la clave viene del archivo .env.
# En Streamlit Cloud ese archivo no existe, porque nunca se sube a
# GitHub: alla la clave se guarda en los Secrets de la aplicacion.
api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        api_key = None

if not api_key:
    st.error(
        "No se encontro la clave GROQ_API_KEY. "
        "En local debe estar en el archivo .env y en Streamlit Cloud "
        "en los Secrets de la aplicacion."
    )
    st.stop()

# Inicializar el cliente de Groq con la clave de API
client = Groq(api_key=api_key)

# Captura la hora actual en la zona horaria de Guatemala
now = datetime.now(ZoneInfo("America/Guatemala"))

# Numero maximo de mensajes que conserva la memoria
MEMORY_MAX_MESSAGES = 10


SYSTEM_PROMPT = f"""
Eres un agente especializado en analisis economico. Hablas en español y respondes
de forma breve, concreta y con lenguaje de analista economico.

La fecha y hora actual es {now.strftime('%d/%m/%Y %H:%M')} (hora de Guatemala).

Objetivo:
- Proporcionar analisis economicos precisos, comparativos y actualizados que apoyen
  la toma de decisiones.
- No respondes temas ajenos a la economia. Si te preguntan algo fuera de ese ambito,
  indicas amablemente que solo atiendes consultas economicas.
- Excepcion a la regla anterior: las preguntas sobre la conversacion misma SI las
  respondes siempre. Eso incluye saludos, el nombre del usuario y lo que ya
  hablaron antes. Por ejemplo, si te preguntan "como me llamo" debes responder con
  el nombre que el usuario te dio, nunca con la negativa de tema ajeno. Lo que
  rechazas son temas de otras materias, como recetas, deportes o cine.

Herramientas de consulta de indicadores:
- consultar_tipo_cambio_api: tipo de cambio actual de una moneda.
- consultar_pib_api: Producto Interno Bruto mas reciente de un pais.
- consultar_inflacion_api: inflacion anual mas reciente de un pais.
- consultar_desempleo_api: tasa de desempleo mas reciente de un pais.
- consultar_balanza_comercial_api: exportaciones, importaciones y saldo comercial.

Herramientas de analisis econometrico:
- regresion_transversal_api: regresion de inflacion contra desempleo usando todos
  los paises del mundo en un mismo anio.
- regresion_temporal_api: regresion de inflacion contra desempleo dentro de un mismo
  pais a lo largo de varios anios.

Reglas para el uso de herramientas:
- Las herramientas que reciben un pais requieren el codigo ISO de 3 letras. Tu debes
  convertir el nombre del pais al codigo antes de llamarlas. Por ejemplo: Guatemala
  es GTM, Mexico es MEX, Estados Unidos es USA, El Salvador es SLV, Honduras es HND,
  Costa Rica es CRI, España es ESP, Argentina es ARG, Colombia es COL, Chile es CHL.
- Los datos que devuelven las herramientas son correctos. Usalos tal cual, sin
  inventar ni ajustar cifras.
- Siempre menciona el anio del dato, porque los indicadores economicos tienen rezago.
- Si necesitas comparar varios paises o varios indicadores, llama a las herramientas
  las veces que sean necesarias.
- Si una herramienta devuelve un error, informalo con claridad y no inventes el dato.

Reglas para no afirmar lo que no consultaste:
- Nunca afirmes tendencias, aumentos, caidas, apreciaciones ni depreciaciones si no
  consultaste datos de mas de un periodo. Las herramientas de indicadores entregan
  un solo dato puntual, no una serie historica.
- Si el usuario pregunta por una tendencia y solo tienes un dato, dilo abiertamente
  o usa regresion_temporal_api, que si trabaja con series historicas.
- No estimes coeficientes, correlaciones ni significancia estadistica por tu cuenta.
  Esos calculos solo provienen de las herramientas de regresion. Si no llamaste a una
  herramienta de regresion, no reportes ningun resultado econometrico.

Reglas para interpretar las regresiones:
- La pendiente indica cuanto cambia la inflacion, en puntos porcentuales, ante un
  aumento de un punto porcentual en el desempleo.
- La R cuadrada indica que proporcion de la variacion de la inflacion queda explicada
  por el desempleo. Un valor bajo significa poder explicativo limitado.
- Si el campo significativa_al_5pct es falso, la relacion no es estadisticamente
  distinguible de cero y asi debes reportarlo.
- La regresion transversal NO es una curva de Phillips. Compara paises distintos en
  un mismo anio y no controla diferencias estructurales entre economias.
- La regresion temporal si corresponde a la especificacion tradicional de la curva
  de Phillips, pero es una regresion simple sin variables de control.
- Cuando una herramienta de regresion incluya una advertencia o nota metodologica,
  debes trasladarsela al usuario.
- Correlacion no implica causalidad. Nunca presentes estos resultados como evidencia
  de que una variable causa la otra.

Despues de entregar las cifras, agrega siempre una interpretacion economica breve
de lo que esos datos significan.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_tipo_cambio_api",
            "description": (
                "Llama a esta funcion para consultar el tipo de cambio actual de una moneda "
                "respecto a las demas monedas del mundo. "
                "Se debe enviar como argumento el codigo de la moneda que se desea consultar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "moneda": {
                        "type": "string",
                        "description": "Codigo de la moneda que se desea consultar, por ejemplo USD"
                    }
                },
                "required": ["moneda"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_pib_api",
            "description": (
                "Llama a esta funcion para consultar el Producto Interno Bruto (PIB) mas "
                "reciente de un pais, expresado en dolares corrientes. "
                "Se debe enviar como argumento el codigo ISO de 3 letras del pais."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 3 letras del pais, por ejemplo GTM para Guatemala"
                    }
                },
                "required": ["pais"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_inflacion_api",
            "description": (
                "Llama a esta funcion para consultar la inflacion anual mas reciente de un "
                "pais, medida por el indice de precios al consumidor. "
                "Se debe enviar como argumento el codigo ISO de 3 letras del pais."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 3 letras del pais, por ejemplo GTM para Guatemala"
                    }
                },
                "required": ["pais"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_desempleo_api",
            "description": (
                "Llama a esta funcion para consultar la tasa de desempleo mas reciente de un "
                "pais, como porcentaje de la fuerza laboral total. "
                "Se debe enviar como argumento el codigo ISO de 3 letras del pais."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 3 letras del pais, por ejemplo GTM para Guatemala"
                    }
                },
                "required": ["pais"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_balanza_comercial_api",
            "description": (
                "Llama a esta funcion para consultar la balanza comercial mas reciente de un "
                "pais. Devuelve exportaciones, importaciones y el saldo comercial, indicando "
                "si hay superavit o deficit. "
                "Se debe enviar como argumento el codigo ISO de 3 letras del pais."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 3 letras del pais, por ejemplo GTM para Guatemala"
                    }
                },
                "required": ["pais"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "regresion_transversal_api",
            "description": (
                "Llama a esta funcion para estimar una regresion lineal simple de la inflacion "
                "contra la tasa de desempleo, usando todos los paises del mundo en un mismo "
                "anio. Cada observacion es un pais distinto. Devuelve pendiente, intercepto, "
                "R cuadrada, error estandar y estadistico t. "
                "Se debe enviar como argumento el anio que se desea analizar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "anio": {
                        "type": "integer",
                        "description": "Anio que se desea analizar, por ejemplo 2024"
                    }
                },
                "required": ["anio"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "regresion_temporal_api",
            "description": (
                "Llama a esta funcion para estimar una regresion lineal simple de la inflacion "
                "contra la tasa de desempleo dentro de un mismo pais a lo largo del tiempo. "
                "Cada observacion es un anio distinto. Corresponde a la especificacion "
                "tradicional de la curva de Phillips. Devuelve pendiente, intercepto, "
                "R cuadrada, error estandar y estadistico t. "
                "Se debe enviar el codigo ISO de 3 letras del pais y opcionalmente el rango "
                "de anios a analizar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 3 letras del pais, por ejemplo GTM para Guatemala"
                    },
                    "anio_inicio": {
                        "type": "integer",
                        "description": "Anio inicial del periodo a analizar. Si no se indica, se usa 1990"
                    },
                    "anio_fin": {
                        "type": "integer",
                        "description": "Anio final del periodo a analizar. Si no se indica, se usa 2025"
                    }
                },
                "required": ["pais"]
            }
        }
    }
]


# =========================
# MEMORIA PARA STREAMLIT
# =========================

# Streamlit vuelve a ejecutar todo el script en cada interaccion.
# Por eso la memoria se guarda en session_state, para que no se
# reinicie cada vez que el usuario escribe un mensaje.

# Se intenta usar la memoria permanente de Supabase.
# Si no hay credenciales o la conexion falla, se usa la memoria
# simple de siempre, para que la aplicacion nunca deje de funcionar.
def crear_memoria():

    url = os.environ.get("SUPABASE_URL")
    clave = os.environ.get("SUPABASE_KEY")

    if not url or not clave:
        try:
            url = st.secrets["SUPABASE_URL"]
            clave = st.secrets["SUPABASE_KEY"]
        except Exception:
            url = None
            clave = None

    if url and clave:
        try:
            from supabase import create_client
            cliente = create_client(url, clave)
            return SupabaseMemory(
                cliente,
                sesion="principal",
                max_messages=MEMORY_MAX_MESSAGES
            ), True
        except Exception as e:
            print(f"No se pudo conectar a Supabase, se usara memoria simple. Error: {e}")

    return BasicMemory(max_messages=MEMORY_MAX_MESSAGES), False


# Se comprueban las dos variables, no solo una. Si la aplicacion se
# actualiza mientras el navegador tiene una sesion abierta, puede
# existir la memoria pero no el dato de que tipo es.
if ("memory" not in st.session_state
        or "memoria_permanente" not in st.session_state):
    st.session_state.memory, st.session_state.memoria_permanente = crear_memoria()

memory = st.session_state.memory
memoria_permanente = st.session_state.memoria_permanente


# =========================
# LOGICA DEL AGENTE
# =========================

def process_response(client: Groq, memory_messages: list[dict], user_text: str):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(memory_messages)
    messages.append({"role": "user", "content": user_text})

    # Se registran las herramientas que el agente decidio utilizar,
    # para poder mostrarlas en la interfaz
    herramientas_usadas = []

    while True:
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            tools=TOOLS
        )

        msg = resp.choices[0].message

        # Si no hay llamados a herramientas, entonces ya regresamos la respuesta
        if not getattr(msg, "tool_calls", None):
            return msg.content or "", herramientas_usadas

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls]
        })

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")

            tools = AdvancedTools()

            if name == "consultar_tipo_cambio_api":
                result = tools.consultar_tipo_cambio_api(
                    moneda=args["moneda"]
                )
            elif name == "consultar_pib_api":
                result = tools.consultar_pib_api(
                    pais=args["pais"]
                )
            elif name == "consultar_inflacion_api":
                result = tools.consultar_inflacion_api(
                    pais=args["pais"]
                )
            elif name == "consultar_desempleo_api":
                result = tools.consultar_desempleo_api(
                    pais=args["pais"]
                )
            elif name == "consultar_balanza_comercial_api":
                result = tools.consultar_balanza_comercial_api(
                    pais=args["pais"]
                )
            elif name == "regresion_transversal_api":
                result = tools.regresion_transversal_api(
                    anio=args["anio"]
                )
            elif name == "regresion_temporal_api":
                result = tools.regresion_temporal_api(
                    pais=args["pais"],
                    anio_inicio=args.get("anio_inicio", 1990),
                    anio_fin=args.get("anio_fin", 2025)
                )
            else:
                print(f"Se intentó llamar a una herramienta desconocida {name}")
                result = {"error": f"Herramienta desconocida: {name}"}

            # Se guarda el nombre de la herramienta y sus argumentos
            herramientas_usadas.append(f"{name} → {args}")

            # Agregar a los mensajes el resultado del llamado de la herramienta
            # Esto lo recibirá el modelo al continuar la iteración
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })


# =========================
# CONFIGURACION STREAMLIT
# =========================

st.title("📊 EconoBot")
st.caption("Agente de analisis economico | Datos del Banco Mundial y tipo de cambio en tiempo real")

with st.sidebar:
    st.header("Herramientas disponibles")
    st.markdown(
        "**Indicadores**\n"
        "- Tipo de cambio\n"
        "- Producto Interno Bruto\n"
        "- Inflacion (IPC anual)\n"
        "- Tasa de desempleo\n"
        "- Balanza comercial\n\n"
        "**Analisis econometrico**\n"
        "- Regresion de corte transversal\n"
        "- Regresion de serie de tiempo"
    )
    st.divider()
    st.caption(f"Memoria: ultimos {MEMORY_MAX_MESSAGES} mensajes")

    if memoria_permanente:
        st.caption("Almacenamiento: Supabase (permanente)")
    else:
        st.caption("Almacenamiento: en sesion (se pierde al recargar)")

    if st.button("Limpiar conversacion"):
        st.session_state.chat_history = []

        # Si la memoria es permanente hay que borrarla de la base
        # de datos; si no, basta con crear una memoria nueva.
        if memoria_permanente:
            memory.limpiar()
        else:
            st.session_state.memory = BasicMemory(max_messages=MEMORY_MAX_MESSAGES)

        st.rerun()


# =========================
# MOSTRAR CONVERSACION
# =========================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for message in st.session_state.chat_history:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Si en ese turno se usaron herramientas, se muestran
        if message.get("herramientas"):
            with st.expander("Herramientas utilizadas"):
                for h in message["herramientas"]:
                    st.code(h, language=None)


# =========================
# ENTRADA DEL USUARIO
# =========================

user_text = st.chat_input("Escribe tu consulta economica...")


if user_text:

    user_text = user_text.strip()

    if user_text:

        # Mostrar mensaje del usuario
        st.session_state.chat_history.append(
            {
                "role": "user",
                "content": user_text
            }
        )

        with st.chat_message("user"):
            st.markdown(user_text)

        # =========================
        # LLAMADA AL AGENTE
        # =========================

        with st.chat_message("assistant"):

            with st.spinner("Consultando datos economicos..."):

                assistant_text, herramientas_usadas = process_response(
                    client,
                    memory.messages(),
                    user_text
                )

            st.markdown(assistant_text)

            if herramientas_usadas:
                with st.expander("Herramientas utilizadas"):
                    for h in herramientas_usadas:
                        st.code(h, language=None)

        # =========================
        # ACTUALIZAR LA MEMORIA
        # =========================

        memory.add("user", user_text)
        memory.add("assistant", assistant_text)

        # Guardar conversación para
        # volver a mostrarla después
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": assistant_text,
                "herramientas": herramientas_usadas
            }
        )
