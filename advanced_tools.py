#######################
# Agente Economico    #
# Herramientas        #
#######################

# Importacion para el manejo de sistema
import os
import requests

# Importacion para el calculo de la raiz cuadrada en la regresion
from math import sqrt

# ------------------------------------------------------------------
# Configuracion de las conexiones a las APIs
# ------------------------------------------------------------------
# Al ejecutar la aplicacion en un servidor en la nube aparecieron dos
# problemas que no se daban en la computadora local:
#   1. Algunos servidores rechazan las peticiones que no se identifican.
#   2. La salida por IPv6 no siempre funciona, y la peticion se queda
#      esperando hasta agotar el tiempo de espera.
# Las siguientes lineas resuelven ambos casos.

CABECERAS = {
    "User-Agent": "EconoBot/1.0 (agente academico de analisis economico)",
    "Accept": "application/json"
}

try:
    import socket
    import urllib3.util.connection as conexion_urllib3

    def _solo_ipv4():
        return socket.AF_INET

    conexion_urllib3.allowed_gai_family = _solo_ipv4
except Exception as e:
    print(f"Aviso: no se pudo forzar el uso de IPv4. {e}")


# Todas las consultas a las APIs pasan por esta funcion,
# para que todas usen las mismas cabeceras.
def _pedir(url: str, timeout: int = 30):
    return requests.get(url, headers=CABECERAS, timeout=timeout)


class AdvancedTools:

    def __init__(self):
        pass

    # ==================================================================
    # HERRAMIENTA 1: TIPO DE CAMBIO
    # API: open.er-api.com (libre, sin autenticacion)
    # ==================================================================
    def consultar_tipo_cambio_api(self, moneda: str):
        print(f"Herramienta consultar_tipo_cambio_api llamada con moneda: {moneda}")

        if not moneda:
            return "Error: Se requiere el codigo de la moneda para obtener el tipo de cambio."

        # URL del servicio para obtener el tipo de cambio segun la moneda:
        url = (
            f"https://open.er-api.com/v6/latest/{moneda.upper()}"
        )

        try:
            response = _pedir(url, 30)
            response.raise_for_status()  # Lanza una excepcion si la respuesta no es exitosa
            return response.json()  # Intentar decodificar la respuesta como JSON
        except Exception as e:
            print(f"Error al consultar_tipo_cambio_api: {moneda}. Error: {e}")
            return f"ERROR: No se pudo obtener el tipo de cambio para la moneda: {moneda}"

    # ==================================================================
    # METODOS INTERNOS DE APOYO PARA EL API DEL BANCO MUNDIAL
    # No son herramientas: el agente no los llama directamente.
    # ==================================================================

    # Consulta un indicador para un solo pais, valor mas reciente
    def _consultar_banco_mundial(self, pais: str, indicador: str):

        # mrv=5 pide los cinco anios mas recientes (most recent values).
        # Se piden varios y no uno solo porque el anio mas reciente a veces
        # viene vacio, y asi se puede tomar el ultimo dato que si exista.
        url = (
            f"https://api.worldbank.org/v2/country/{pais.upper()}"
            f"/indicator/{indicador}?format=json&mrv=5"
        )

        # Se hacen hasta tres intentos porque una falla momentanea de red
        # no significa que el dato no exista.
        data = None
        for intento in range(3):
            try:
                response = _pedir(url, 30)
                response.raise_for_status()
                data = response.json()
                break
            except Exception as e:
                print(f"Intento {intento + 1} fallido para {indicador} en {pais}. Error: {e}")
                data = None

        if data is None:
            return None

        # El Banco Mundial responde una lista de dos bloques: [metadata, [filas]]
        # Si el pais o el indicador son invalidos, responde codigo 200 pero
        # con un solo bloque que contiene un mensaje de error.
        if not isinstance(data, list) or len(data) < 2 or not data[1]:
            return None

        # Las filas vienen del anio mas reciente al mas antiguo, asi que se
        # recorre en orden y se toma la primera que traiga un valor.
        for fila in data[1]:
            if fila.get("value") is not None:
                return {
                    "pais": fila["country"]["value"],
                    "indicador": fila["indicator"]["value"],
                    "anio": fila["date"],
                    "valor": fila["value"]
                }

        # Ninguno de los anios consultados tenia dato
        return None

    # Obtiene la lista de paises reales, excluyendo los agregados regionales.
    # El Banco Mundial mezcla paises con agregados como "World", "Euro area" o
    # "Latin America & Caribbean". Si no se filtran, un mismo pais se cuenta
    # varias veces y la regresion queda contaminada.
    # Los agregados se identifican porque su region tiene id "NA".
    def _obtener_paises_reales(self):

        url = "https://api.worldbank.org/v2/country?format=json&per_page=400"

        try:
            response = _pedir(url, 30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error al obtener la lista de paises. Error: {e}")
            return None

        if not isinstance(data, list) or len(data) < 2 or not data[1]:
            return None

        paises = set()
        for fila in data[1]:
            region = fila.get("region", {})
            if region.get("id") != "NA":
                paises.add(fila["id"])

        return paises

    # Consulta un indicador para todos los paises en un anio especifico
    def _consultar_indicador_todos(self, indicador: str, anio: int):

        url = (
            f"https://api.worldbank.org/v2/country/all/indicator/{indicador}"
            f"?format=json&date={anio}&per_page=400"
        )

        try:
            response = _pedir(url, 60)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error al consultar {indicador} para el anio {anio}. Error: {e}")
            return None

        if not isinstance(data, list) or len(data) < 2 or not data[1]:
            return None

        # Se arma un diccionario: codigo del pais -> valor del indicador
        valores = {}
        for fila in data[1]:
            codigo = fila.get("countryiso3code")
            valor = fila.get("value")
            if codigo and valor is not None:
                valores[codigo] = valor

        return valores

    # Consulta la serie historica de un indicador para un solo pais
    def _consultar_serie_pais(self, pais: str, indicador: str,
                              anio_inicio: int, anio_fin: int):

        url = (
            f"https://api.worldbank.org/v2/country/{pais.upper()}"
            f"/indicator/{indicador}"
            f"?format=json&date={anio_inicio}:{anio_fin}&per_page=200"
        )

        try:
            response = _pedir(url, 60)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error al consultar la serie de {indicador} para {pais}. Error: {e}")
            return None

        if not isinstance(data, list) or len(data) < 2 or not data[1]:
            return None

        # Se arma un diccionario: anio -> valor del indicador
        serie = {}
        for fila in data[1]:
            anio = fila.get("date")
            valor = fila.get("value")
            if anio and valor is not None:
                serie[anio] = valor

        return serie

    # Calcula una regresion lineal simple por minimos cuadrados ordinarios.
    # Modelo estimado:  y = intercepto + pendiente * x
    # Devuelve tambien R cuadrada, el error estandar de la pendiente y el
    # estadistico t, que sirve para evaluar la significancia estadistica.
    def _regresion_lineal(self, x: list, y: list):

        n = len(x)
        if n < 3:
            return None

        media_x = sum(x) / n
        media_y = sum(y) / n

        sxx = sum((xi - media_x) ** 2 for xi in x)
        sxy = sum((x[i] - media_x) * (y[i] - media_y) for i in range(n))
        syy = sum((yi - media_y) ** 2 for yi in y)

        # Si no hay variacion en alguna variable, la regresion no esta definida
        if sxx == 0 or syy == 0:
            return None

        pendiente = sxy / sxx
        intercepto = media_y - pendiente * media_x

        # Coeficiente de correlacion y coeficiente de determinacion
        r = sxy / sqrt(sxx * syy)
        r_cuadrada = r ** 2

        # Suma de cuadrados del error y varianza residual
        sce = syy - pendiente * sxy
        varianza_residual = sce / (n - 2)

        if varianza_residual > 0:
            error_estandar = sqrt(varianza_residual / sxx)
            estadistico_t = pendiente / error_estandar
        else:
            error_estandar = 0.0
            estadistico_t = 0.0

        return {
            "n_observaciones": n,
            "pendiente": round(pendiente, 4),
            "intercepto": round(intercepto, 4),
            "r_cuadrada": round(r_cuadrada, 4),
            "correlacion": round(r, 4),
            "error_estandar_pendiente": round(error_estandar, 4),
            "estadistico_t": round(estadistico_t, 4),
            "significativa_al_5pct": abs(estadistico_t) > 2
        }

    # ==================================================================
    # HERRAMIENTA 2: PRODUCTO INTERNO BRUTO (PIB)
    # Indicador Banco Mundial: NY.GDP.MKTP.CD
    # ==================================================================
    def consultar_pib_api(self, pais: str):
        print(f"Herramienta consultar_pib_api llamada con pais: {pais}")

        if not pais:
            return "Error: Se requiere el codigo del pais para obtener el PIB."

        resultado = self._consultar_banco_mundial(pais, "NY.GDP.MKTP.CD")

        if resultado is None:
            return f"ERROR: No se pudo obtener el PIB para el pais: {pais}"

        resultado["unidad"] = "dolares corrientes"
        return resultado

    # ==================================================================
    # HERRAMIENTA 3: INFLACION (INDICE DE PRECIOS AL CONSUMIDOR)
    # Indicador Banco Mundial: FP.CPI.TOTL.ZG
    # ==================================================================
    def consultar_inflacion_api(self, pais: str):
        print(f"Herramienta consultar_inflacion_api llamada con pais: {pais}")

        if not pais:
            return "Error: Se requiere el codigo del pais para obtener la inflacion."

        resultado = self._consultar_banco_mundial(pais, "FP.CPI.TOTL.ZG")

        if resultado is None:
            return f"ERROR: No se pudo obtener la inflacion para el pais: {pais}"

        resultado["unidad"] = "porcentaje de variacion anual"
        return resultado

    # ==================================================================
    # HERRAMIENTA 4: TASA DE DESEMPLEO
    # Indicador Banco Mundial: SL.UEM.TOTL.ZS
    # ==================================================================
    def consultar_desempleo_api(self, pais: str):
        print(f"Herramienta consultar_desempleo_api llamada con pais: {pais}")

        if not pais:
            return "Error: Se requiere el codigo del pais para obtener el desempleo."

        resultado = self._consultar_banco_mundial(pais, "SL.UEM.TOTL.ZS")

        if resultado is None:
            return f"ERROR: No se pudo obtener el desempleo para el pais: {pais}"

        resultado["unidad"] = "porcentaje de la fuerza laboral total"
        return resultado

    # ==================================================================
    # HERRAMIENTA 5: BALANZA COMERCIAL
    # Indicadores Banco Mundial:
    #   Exportaciones -> NE.EXP.GNFS.CD
    #   Importaciones -> NE.IMP.GNFS.CD
    # ==================================================================
    def consultar_balanza_comercial_api(self, pais: str):
        print(f"Herramienta consultar_balanza_comercial_api llamada con pais: {pais}")

        if not pais:
            return "Error: Se requiere el codigo del pais para obtener la balanza comercial."

        exportaciones = self._consultar_banco_mundial(pais, "NE.EXP.GNFS.CD")
        importaciones = self._consultar_banco_mundial(pais, "NE.IMP.GNFS.CD")

        if exportaciones is None or importaciones is None:
            return f"ERROR: No se pudo obtener la balanza comercial para el pais: {pais}"

        saldo = exportaciones["valor"] - importaciones["valor"]

        return {
            "pais": exportaciones["pais"],
            "anio": exportaciones["anio"],
            "exportaciones": exportaciones["valor"],
            "importaciones": importaciones["valor"],
            "saldo_comercial": saldo,
            "resultado": "superavit" if saldo > 0 else "deficit",
            "unidad": "dolares corrientes"
        }

    # ==================================================================
    # HERRAMIENTA 6: REGRESION DE CORTE TRANSVERSAL
    # Regresa la inflacion contra el desempleo usando todos los paises
    # del mundo en un mismo anio. Cada observacion es un pais distinto.
    # ==================================================================
    def regresion_transversal_api(self, anio: int):
        print(f"Herramienta regresion_transversal_api llamada con anio: {anio}")

        if not anio:
            return "Error: Se requiere el anio para realizar la regresion transversal."

        try:
            anio = int(anio)
        except Exception:
            return f"ERROR: El anio proporcionado no es valido: {anio}"

        # Se obtiene la lista de paises reales para excluir agregados regionales
        paises_reales = self._obtener_paises_reales()
        if paises_reales is None:
            return "ERROR: No se pudo obtener la lista de paises del Banco Mundial."

        inflacion = self._consultar_indicador_todos("FP.CPI.TOTL.ZG", anio)
        desempleo = self._consultar_indicador_todos("SL.UEM.TOTL.ZS", anio)

        if not inflacion or not desempleo:
            return f"ERROR: No se pudieron obtener los datos para el anio {anio}."

        # Se cruzan ambos indicadores: solo entran los paises que tienen
        # dato de inflacion Y dato de desempleo, y que no son agregados.
        x = []  # desempleo, variable independiente
        y = []  # inflacion, variable dependiente

        for codigo in inflacion:
            if codigo in desempleo and codigo in paises_reales:
                x.append(desempleo[codigo])
                y.append(inflacion[codigo])

        if len(x) < 3:
            return f"ERROR: Datos insuficientes para el anio {anio}. Solo {len(x)} paises."

        # Regresion con todos los paises
        completa = self._regresion_lineal(x, y)

        # Regresion excluyendo casos de inflacion extrema (mayor a 50%).
        # Las hiperinflaciones distorsionan fuertemente una regresion simple.
        x_filtrado = []
        y_filtrado = []
        atipicos = 0
        for i in range(len(x)):
            if abs(y[i]) <= 50:
                x_filtrado.append(x[i])
                y_filtrado.append(y[i])
            else:
                atipicos += 1

        sin_atipicos = self._regresion_lineal(x_filtrado, y_filtrado)

        return {
            "tipo_de_analisis": "corte transversal entre paises",
            "anio": anio,
            "variable_dependiente": "inflacion anual (%)",
            "variable_independiente": "tasa de desempleo (%)",
            "paises_incluidos": len(x),
            "casos_de_inflacion_extrema_excluidos": atipicos,
            "regresion_con_todos_los_paises": completa,
            "regresion_sin_inflacion_extrema": sin_atipicos,
            "advertencia_metodologica": (
                "Cada observacion es un pais distinto en un mismo anio. Esta "
                "especificacion NO estima una curva de Phillips, porque la relacion "
                "de Phillips es un fenomeno de series de tiempo dentro de una misma "
                "economia. Las diferencias entre paises responden a factores "
                "estructurales como regimen cambiario, informalidad laboral y "
                "credibilidad del banco central, que aqui no estan controlados."
            )
        }

    # ==================================================================
    # HERRAMIENTA 7: REGRESION DE SERIE DE TIEMPO
    # Regresa la inflacion contra el desempleo dentro de un mismo pais
    # a lo largo de varios anios. Cada observacion es un anio distinto.
    # Esta es la especificacion correcta de la curva de Phillips.
    # ==================================================================
    def regresion_temporal_api(self, pais: str, anio_inicio: int = 1990,
                               anio_fin: int = 2025):
        print(f"Herramienta regresion_temporal_api llamada con pais: {pais}, "
              f"periodo: {anio_inicio}-{anio_fin}")

        if not pais:
            return "Error: Se requiere el codigo del pais para realizar la regresion."

        try:
            anio_inicio = int(anio_inicio)
            anio_fin = int(anio_fin)
        except Exception:
            return "ERROR: Los anios proporcionados no son validos."

        if anio_inicio >= anio_fin:
            return "ERROR: El anio inicial debe ser menor que el anio final."

        inflacion = self._consultar_serie_pais(
            pais, "FP.CPI.TOTL.ZG", anio_inicio, anio_fin)
        desempleo = self._consultar_serie_pais(
            pais, "SL.UEM.TOTL.ZS", anio_inicio, anio_fin)

        if not inflacion or not desempleo:
            return f"ERROR: No se pudieron obtener las series para el pais: {pais}"

        # Se cruzan ambas series: solo entran los anios con dato en ambas
        anios_comunes = sorted(set(inflacion.keys()) & set(desempleo.keys()))

        x = []  # desempleo, variable independiente
        y = []  # inflacion, variable dependiente

        for anio in anios_comunes:
            x.append(desempleo[anio])
            y.append(inflacion[anio])

        if len(x) < 3:
            return (f"ERROR: Datos insuficientes para {pais}. "
                    f"Solo {len(x)} anios con informacion completa.")

        resultado = self._regresion_lineal(x, y)

        if resultado is None:
            return f"ERROR: No se pudo estimar la regresion para el pais: {pais}"

        return {
            "tipo_de_analisis": "serie de tiempo dentro de un pais",
            "pais": pais.upper(),
            "periodo": f"{anios_comunes[0]}-{anios_comunes[-1]}",
            "variable_dependiente": "inflacion anual (%)",
            "variable_independiente": "tasa de desempleo (%)",
            "anios_incluidos": len(x),
            "inflacion_promedio": round(sum(y) / len(y), 4),
            "desempleo_promedio": round(sum(x) / len(x), 4),
            "regresion": resultado,
            "nota_metodologica": (
                "Esta es la especificacion tradicional de la curva de Phillips: "
                "una pendiente negativa indica relacion inversa entre desempleo e "
                "inflacion. Es una regresion simple sin variables de control ni "
                "correccion de autocorrelacion, por lo que debe leerse como "
                "evidencia descriptiva y no como una estimacion causal."
            )
        }
