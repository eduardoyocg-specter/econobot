#################################
# Agente de Analisis Economico  #
# Memoria permanente (Supabase) #
#################################

# Esta memoria funciona igual que basic_memory.py desde afuera:
# tiene los metodos add() y messages(), asi que el agente no nota
# la diferencia. El cambio es donde se guardan los mensajes.
#
#   basic_memory.py  -> los guarda en la memoria del programa,
#                       y se pierden al cerrar o recargar.
#   supabase_memory  -> los guarda en una base de datos en linea,
#                       asi que sobreviven aunque se recargue.


class SupabaseMemory:

    def __init__(self, cliente, sesion: str = "principal",
                 max_messages: int = 10):
        self.cliente = cliente
        self.sesion = sesion
        self.max_messages = max_messages
        self.tabla = "mensajes"

    # Guarda un mensaje nuevo en la base de datos
    def add(self, role: str, text: str):
        try:
            self.cliente.table(self.tabla).insert({
                "sesion": self.sesion,
                "rol": role,
                "contenido": text
            }).execute()
        except Exception as e:
            print(f"No se pudo guardar el mensaje en Supabase. Error: {e}")

    # Devuelve los ultimos mensajes, del mas antiguo al mas reciente
    def messages(self):
        try:
            respuesta = (
                self.cliente.table(self.tabla)
                .select("rol, contenido")
                .eq("sesion", self.sesion)
                .order("id", desc=True)
                .limit(self.max_messages)
                .execute()
            )

            # La consulta pide los mas recientes primero, por eso
            # se invierte el orden antes de devolverlos.
            filas = list(reversed(respuesta.data or []))

            return [
                {"role": fila["rol"], "content": fila["contenido"]}
                for fila in filas
            ]
        except Exception as e:
            print(f"No se pudo leer la memoria de Supabase. Error: {e}")
            return []

    # Borra la conversacion guardada
    def limpiar(self):
        try:
            (self.cliente.table(self.tabla)
             .delete()
             .eq("sesion", self.sesion)
             .execute())
        except Exception as e:
            print(f"No se pudo limpiar la memoria en Supabase. Error: {e}")
