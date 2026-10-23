
import time
from collections import deque

import numpy as np
import pandas as pd
import plotly.express as px
import serial
import serial.tools.list_ports
import streamlit as st

st.set_page_config(
    page_title="Monitor IoT | ESP32",
    page_icon="🌡️",
    layout="wide",
)

# ---------- Estado de la aplicación ----------

if "serial_conn" not in st.session_state:
    st.session_state.serial_conn = None

if "mediciones" not in st.session_state:
    st.session_state.mediciones = None

if "termica" not in st.session_state:
    st.session_state.termica = None

if "historial" not in st.session_state:
    st.session_state.historial = deque(maxlen=600)

if "ultimo_dato" not in st.session_state:
    st.session_state.ultimo_dato = None

if "ultimo_error" not in st.session_state:
    st.session_state.ultimo_error = ""

if "ultima_lectura" not in st.session_state:
    st.session_state.ultima_lectura = None

if "tramas_therm_vistas" not in st.session_state:
    st.session_state.tramas_therm_vistas = 0

if "tramas_therm_validas" not in st.session_state:
    st.session_state.tramas_therm_validas = 0

if "tramas_therm_invalidas" not in st.session_state:
    st.session_state.tramas_therm_invalidas = 0

if "ultima_therm_vista" not in st.session_state:
    st.session_state.ultima_therm_vista = None

if "longitud_therm" not in st.session_state:
    st.session_state.longitud_therm = 0

def desconectar():
    conexion = st.session_state.serial_conn

    if conexion is not None:
        try:
            conexion.close()
        except (serial.SerialException, OSError):
            pass

    st.session_state.serial_conn = None


def procesar_linea(linea):
    """Interpreta las tramas DATA y THERM del firmware Arduino."""
    partes = linea.split(",")

    # DATA,presencia,movimiento,rango,distancia,corazon,respira
    if partes[0] == "DATA" and len(partes) == 7:
        try:
            datos = {
                "presencia": int(partes[1]),
                "movimiento": int(partes[2]),
                "rango": int(partes[3]),
                "distancia": int(partes[4]),
                "corazon": int(partes[5]),
                "respiracion": int(partes[6]),
                "hora": time.strftime("%H:%M:%S"),
                "timestamp": time.time(),
            }

            st.session_state.mediciones = datos
            st.session_state.ultimo_dato = time.time()
            st.session_state.historial.append(datos)

        except ValueError:
            st.session_state.ultimo_error = (
                "Se recibió una trama DATA con valores no numéricos."
            )

    # THERM + 768 temperaturas en décimas de grado Celsius
    elif partes[0] == "THERM" and len(partes) == 769:
        try:
            temperaturas = np.array(
                [int(valor) / 10.0 for valor in partes[1:]],
                dtype=float,
            )

            st.session_state.termica = temperaturas.reshape(24, 32)
            st.session_state.ultima_lectura = time.time()

        except ValueError:
            st.session_state.ultimo_error = (
                "Se recibió una trama térmica incorrecta."
            )



def leer_serial():
    conexion = st.session_state.serial_conn

    if conexion is None or not conexion.is_open:
        return

    for _ in range(100):
        try:
            if conexion.in_waiting == 0:
                break

            linea = conexion.readline().decode(
                "utf-8", errors="ignore"
            ).strip()

            if not linea:
                continue

            
            if linea.startswith("THERM"):
                partes = linea.split(",")

                st.session_state.tramas_therm_vistas += 1
                st.session_state.ultima_therm_vista = time.time()
                st.session_state.longitud_therm = len(partes) - 1

                if len(partes) != 769:
                    st.session_state.tramas_therm_invalidas += 1
                    st.session_state.ultimo_error = (
                        f"Trama térmica incompleta: "
                        f"{len(partes) - 1} de 768 temperaturas."
                    )
                    continue

                try:
                    valores = [
                        int(valor) / 10.0
                        for valor in partes[1:]
                    ]

                    matriz = np.array(
                        valores, dtype=float
                    ).reshape(24, 32)

                    st.session_state.termica = matriz
                    st.session_state.ultima_lectura = time.time()
                    st.session_state.tramas_therm_validas += 1
                    st.session_state.ultimo_error = ""

                except (ValueError, OverflowError) as error:
                    st.session_state.tramas_therm_invalidas += 1
                    st.session_state.ultimo_error = (
                        f"Error al interpretar THERM: {error}"
                    )

                    st.session_state.ultimo_error = (
                        f"Trama térmica incompleta: "
                        f"{len(partes) - 1} de 768 temperaturas."
                    )
                    continue

                try:
                    valores = [
                        int(valor) / 10.0
                        for valor in partes[1:]
                    ]

                    matriz = np.array(
                        valores, dtype=float
                    ).reshape(24, 32)

                    st.session_state.termica = matriz
                    st.session_state.ultima_lectura = time.time()
                    st.session_state.ultimo_error = ""

                except ValueError:
                    st.session_state.ultimo_error = (
                        "La trama THERM contiene valores no numéricos."
                    )

            elif linea.startswith("DATA,"):
                procesar_linea(linea)

        except (serial.SerialException, OSError) as error:
            st.session_state.ultimo_error = str(error)
            desconectar()
            break



# ---------- Encabezado ----------

st.title("🌡️ Sistema de monitoreo IoT")
st.caption(
    "ESP32 NodeMCU · DFRobot C1001 · MLX90640"
)

# ---------- Panel lateral ----------

with st.sidebar:
    st.header("Conexión con ESP32")

    puertos = [
        puerto.device
        for puerto in serial.tools.list_ports.comports()
    ]

    if puertos:
        puerto_elegido = st.selectbox(
            "Puerto USB",
            puertos,
            help="Selecciona el puerto COM de tu ESP32.",
        )
    else:
        puerto_elegido = st.text_input(
            "Puerto USB",
            placeholder="COM3",
        )
        st.caption(
            "No se detectaron puertos. Comprueba el cable USB."
        )

    velocidad = st.selectbox(
        "Velocidad de comunicación",
        [115200, 460800],
        index=0,
    )

    if st.button("Conectar", type="primary", use_container_width=True):
        desconectar()

        if puerto_elegido:
            try:
                conexion = serial.Serial(
                    puerto_elegido,
                    baudrate=velocidad,
                    timeout=1.0,
                )

                # El ESP32 puede reiniciarse al abrir el puerto.
                time.sleep(2)
                conexion.reset_input_buffer()

                st.session_state.serial_conn = conexion
                st.session_state.ultimo_error = ""

                st.rerun()

            except (serial.SerialException, OSError) as error:
                st.error(f"No se pudo conectar: {error}")

    if st.button("Desconectar", use_container_width=True):
        desconectar()
        st.rerun()

    conectado = (
        st.session_state.serial_conn is not None
        and st.session_state.serial_conn.is_open
    )

    if conectado:
        st.success("Puerto serie conectado")
    else:
        st.warning("Puerto serie desconectado")

    st.divider()
    st.caption("Baudios del firmware: 115200")
    st.caption(
        "Cierra el Monitor Serie del Arduino IDE antes de conectar."
    )

    if st.session_state.ultimo_error:
        st.error(st.session_state.ultimo_error)


# ---------- Panel de mediciones en vivo ----------

@st.fragment(run_every=0.5)
def dashboard():
    leer_serial()

    datos = st.session_state.mediciones
    conectado = (
        st.session_state.serial_conn is not None
        and st.session_state.serial_conn.is_open
    )

    if not conectado:
        st.info(
            "Conecta el ESP32 desde el panel lateral para comenzar."
        )

    if datos is not None:
        ahora = time.time()
        edad = ahora - st.session_state.ultimo_dato

        if edad > 5:
            st.warning(
                "No llegan nuevas tramas DATA. "
                "Comprueba el cable USB y el programa del ESP32."
            )

        st.subheader("Mediciones del C1001")

        presencia = datos["presencia"]
        texto_presencia = (
            "Detectada" if presencia != 0 else "No detectada"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric("Presencia humana", texto_presencia)
        c2.metric("Distancia reportada", f'{datos["distancia"]}')
        c3.metric("Movimiento", f'{datos["movimiento"]}')

        c4, c5, c6 = st.columns(3)

        c4.metric("Rango de movimiento", f'{datos["rango"]}')
        c5.metric("Frecuencia cardíaca", f'{datos["corazon"]} bpm')
        c6.metric("Respiración", f'{datos["respiracion"]}')

        st.caption(
            "La distancia y el rango se muestran como valores "
            "reportados por la biblioteca. Verifica sus unidades "
            "en la documentación del C1001."
        )

    # ---------- Mapa térmico ----------

    st.divider()
    st.subheader("Imagen térmica MLX90640")
    
    d1, d2, d3 = st.columns(3)

    d1.metric(
        "Tramas THERM recibidas",
        st.session_state.tramas_therm_vistas
    )

    d2.metric(
        "Tramas válidas",
        st.session_state.tramas_therm_validas
    )

    d3.metric(
        "Tramas incompletas/erróneas",
        st.session_state.tramas_therm_invalidas
    )

    if st.session_state.ultima_therm_vista is not None:
        segundos = (
            time.time() - st.session_state.ultima_therm_vista
        )
        st.caption(
            f"Última trama THERM recibida hace {segundos:.1f} s. "
            f"Temperaturas detectadas en la última trama: "
            f"{st.session_state.longitud_therm}."
        )

    matriz = st.session_state.termica

    if matriz is not None:
        col_mapa, col_stats = st.columns([3, 1])

        with col_mapa:
            figura = px.imshow(
                matriz,
                color_continuous_scale="Inferno",
                origin="upper",
                aspect="auto",
                labels={
                    "x": "Columna del sensor",
                    "y": "Fila del sensor",
                    "color": "Temperatura (°C)",
                },
            )

            figura.update_layout(
                height=480,
                margin=dict(l=10, r=10, t=20, b=10),
            )

            figura.update_xaxes(
                dtick=4,
                constrain="domain",
            )
            figura.update_yaxes(dtick=4)

            st.plotly_chart(
                figura,
                use_container_width=True,
            )

        with col_stats:
            st.metric("Mínima", f"{np.nanmin(matriz):.1f} °C")
            st.metric("Máxima", f"{np.nanmax(matriz):.1f} °C")
            st.metric("Promedio", f"{np.nanmean(matriz):.1f} °C")

            if st.session_state.ultima_lectura is not None:
                segundos = time.time() - st.session_state.ultima_lectura
                st.caption(
                    f"Última trama térmica hace {segundos:.1f} s"
                )

    else:
        st.warning(
            "Todavía no se ha recibido una trama térmica válida."
        )

        st.write("**Diagnóstico del MLX90640**")
        st.write("Puerto serie conectado:", conectado)
        st.write(
            "Última trama térmica:",
            st.session_state.ultima_lectura
        )

        if st.session_state.ultimo_error:
            st.error(st.session_state.ultimo_error)

    # ---------- Historial ----------

    st.divider()
    st.subheader("Historial de mediciones")

    historial = list(st.session_state.historial)

    if historial:
        df = pd.DataFrame(historial)

        variables = {
            "corazon": "Frecuencia cardíaca",
            "respiracion": "Respiración",
            "distancia": "Distancia reportada",
            "rango": "Rango de movimiento",
        }

        variable = st.selectbox(
            "Variable para el gráfico",
            options=list(variables.keys()),
            format_func=lambda x: variables[x],
            key="variable_historial",
        )

        figura_linea = px.line(
            df,
            x="timestamp",
            y=variable,
            markers=True,
            labels={
                "timestamp": "Hora",
                variable: variables[variable],
            },
        )

        figura_linea.update_layout(
            height=350,
            margin=dict(l=10, r=10, t=20, b=10),
        )
        figura_linea.update_xaxes(
            tickformat="%H:%M:%S",
            title="Hora",
        )

        st.plotly_chart(
            figura_linea,
            use_container_width=True,
        )

        csv = df.drop(columns=["timestamp"]).to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Descargar mediciones CSV",
            data=csv,
            file_name="mediciones_esp32.csv",
            mime="text/csv",
        )

        st.caption(
            f"Registros almacenados en esta sesión: {len(df)}"
        )

    else:
        st.caption(
            "Los gráficos aparecerán después de recibir las primeras tramas DATA."
        )

    st.caption(
        "Proyecto experimental: estas lecturas no constituyen "
        "un diagnóstico médico ni sustituyen equipos clínicos."
    )


dashboard()
