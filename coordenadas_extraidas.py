import streamlit as st
import zipfile
import xml.etree.ElementTree as ET
import re
import folium
from simplekml import Kml
from io import BytesIO

# ============================================
# Código do Extrator (não alterado)
# ============================================

def gms_to_decimal(gms_str):
    match = re.match(r"(-?\d+)°(\d+)'([\d\.]+)\"?", gms_str.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Formato inválido: {gms_str}")
    graus, minutos, segundos = map(float, match.groups())
    decimal = abs(graus) + (minutos / 60) + (segundos / 3600)
    return -decimal if graus < 0 else decimal

def decimal_to_gms(coord, is_latitude=True):
    abs_val = abs(coord)
    graus = int(abs_val)
    minutos = int((abs_val - graus) * 60)
    segundos = (abs_val - graus - minutos / 60) * 3600
    sinal = "-" if coord < 0 else ""
    return f"{sinal}{graus}°{minutos:02d}'{segundos:.2f}\""

# Gerenciamento de estado para o extrator
if 'coordinates' not in st.session_state:
    st.session_state.coordinates = []

def adicionar_coordenadas_manual(texto):
    linhas = texto.strip().split("\n")
    errors = []
    for linha in linhas:
        partes = linha.strip().split()
        if len(partes) < 2:
            errors.append(f"Formato inválido na linha: {linha}")
            continue
        try:
            lat_gms, lon_gms = partes[:2]
            lat_decimal = gms_to_decimal(lat_gms)
            lon_decimal = gms_to_decimal(lon_gms)
            st.session_state.coordinates.append((lat_decimal, lon_decimal))
        except Exception as e:
            errors.append(f"Erro na linha: {linha} - {e}")
    return errors

def limpar():
    st.session_state.coordinates = []

def gerar_poligono():
    if not st.session_state.coordinates:
        st.error("Nenhuma coordenada inserida.")
        return None
    lat_media = sum(lat for lat, lon in st.session_state.coordinates) / len(st.session_state.coordinates)
    lon_media = sum(lon for lat, lon in st.session_state.coordinates) / len(st.session_state.coordinates)
    mapa = folium.Map(location=[lat_media, lon_media], zoom_start=15)
    folium.Polygon(locations=st.session_state.coordinates, color="blue", fill=True, fill_opacity=0.4).add_to(mapa)
    return mapa

def exportar_kmz():
    if not st.session_state.coordinates:
        st.error("Nenhuma coordenada inserida para exportação.")
        return None
    kml = Kml()
    pol = kml.newpolygon(name="Polígono")
    coords_kml = [(lon, lat, 0) for lat, lon in st.session_state.coordinates]
    if coords_kml[0] != coords_kml[-1]:
        coords_kml.append(coords_kml[0])
    pol.outerboundaryis = coords_kml
    kmz_buffer = BytesIO()
    kml.savekmz(kmz_buffer)
    kmz_buffer.seek(0)
    return kmz_buffer

def carregar_kml_kmz(uploaded_file):
    if uploaded_file is None:
        return "Nenhum arquivo enviado."
    coordenadas_extraidas = []
    try:
        if uploaded_file.name.endswith(".kmz"):
            with zipfile.ZipFile(uploaded_file, "r") as kmz:
                kml_file = [f for f in kmz.namelist() if f.endswith(".kml")][0]
                with kmz.open(kml_file) as kml:
                    tree = ET.parse(kml)
        else:
            tree = ET.parse(uploaded_file)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        for placemark in root.findall(".//kml:Placemark", ns):
            for polygon in placemark.findall(".//kml:Polygon", ns):
                for outer in polygon.findall(".//kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
                    coord_text = outer.text.strip()
                    coords = coord_text.split()
                    for coord in coords:
                        lon, lat, *_ = map(float, coord.split(","))
                        coordenadas_extraidas.append((lat, lon))
        if len(coordenadas_extraidas) > 1 and coordenadas_extraidas[0] == coordenadas_extraidas[-1]:
            coordenadas_extraidas.pop()
        st.session_state.coordinates = coordenadas_extraidas
        return "Coordenadas extraídas com sucesso!"
    except Exception as e:
        return f"Erro ao carregar o arquivo KML/KMZ: {e}"

# Função para o submenu do Extrator
def extrator():
    st.header("Extrator de Coordenadas KML/KMZ")
    operacao = st.radio("Escolha a operação:", 
                        ["Inserção Manual", "Carregar Arquivo", "Gerar Polígono", "Exportar KMZ", "Limpar Coordenadas"])

    if operacao == "Inserção Manual":
        st.subheader("Inserção Manual de Coordenadas")
        texto = st.text_area("Insira múltiplas coordenadas (ex: -24°01'37.72\" -49°21'42.51\")")
        if st.button("Adicionar Coordenadas Manualmente"):
            erros = adicionar_coordenadas_manual(texto)
            if erros:
                for erro in erros:
                    st.error(erro)
            else:
                st.success("Coordenadas adicionadas com sucesso!")
        st.write("**Coordenadas Atuais:**")
        if st.session_state.coordinates:
            for i, (lat, lon) in enumerate(st.session_state.coordinates, 1):
                st.write(f"{i}. {decimal_to_gms(lat)} {decimal_to_gms(lon, is_latitude=False)}")
        else:
            st.info("Nenhuma coordenada registrada.")

    elif operacao == "Carregar Arquivo":
        st.subheader("Carregar Arquivo KML/KMZ")
        uploaded_file = st.file_uploader("Carregar arquivo", type=["kml", "kmz"])
        if uploaded_file is not None:
            mensagem = carregar_kml_kmz(uploaded_file)
            if "sucesso" in mensagem.lower():
                st.success(mensagem)
            else:
                st.error(mensagem)
            st.write("**Coordenadas Extraídas:**")
            if st.session_state.coordinates:
                for i, (lat, lon) in enumerate(st.session_state.coordinates, 1):
                    st.write(f"{i}. {decimal_to_gms(lat)} {decimal_to_gms(lon, is_latitude=False)}")
            else:
                st.info("Nenhuma coordenada registrada.")

    elif operacao == "Gerar Polígono":
        st.subheader("Gerar Polígono")
        if st.button("Gerar Polígono"):
            mapa = gerar_poligono()
            if mapa:
                mapa_html = mapa._repr_html_()
                st.components.v1.html(mapa_html, height=500)

    elif operacao == "Exportar KMZ":
        st.subheader("Exportar KMZ")
        if st.button("Exportar KMZ"):
            kmz_buffer = exportar_kmz()
            if kmz_buffer:
                st.download_button(label="Download KMZ", data=kmz_buffer, file_name="poligono.kmz", mime="application/vnd.google-earth.kmz")

    elif operacao == "Limpar Coordenadas":
        st.subheader("Limpar Coordenadas")
        if st.button("Limpar Coordenadas"):
            limpar()
            st.success("Coordenadas limpas!")

import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime

# --------------------------------------------
# Função para gerar o PDF do RIT
# --------------------------------------------
def gerar_pdf_rit(
    rit_num, data, opm, municipio, tipo_area, endereco, numeral, complemento, 
    ponto_referencia, latitude_acesso, documento_referencia, auto_referencia, 
    numero_car, autorizacoes, tipo_bioma, embargo, area, fontes_dados, 
    escala, centroide_lat, centroide_lon, fonte, analise
):
    # Cria um buffer em memória para receber o PDF
    buffer = BytesIO()

    # Define o objeto Canvas, passando o buffer e o tamanho da página
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4  # Largura e altura da página A4

    # Exemplo de título
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "Relatório de Informações Técnicas (RIT)")

    # Exemplo de dados do formulário
    c.setFont("Helvetica", 10)
    linha_atual = height - 80  # posição vertical inicial

    # Helper para escrever texto linha a linha
    def escreve_campo(label, valor):
        nonlocal linha_atual
        c.drawString(50, linha_atual, f"{label}: {valor}")
        linha_atual -= 15  # avança uma linha

    escreve_campo("RIT Nº", rit_num)
    escreve_campo("Data", str(data))
    escreve_campo("OPM", opm)
    escreve_campo("Município", municipio)
    escreve_campo("Tipo de Área", tipo_area)
    escreve_campo("Endereço", endereco)
    escreve_campo("Número", numeral)
    escreve_campo("Complemento", complemento)
    escreve_campo("Ponto de Referência", ponto_referencia)
    escreve_campo("Latitude do Acesso", latitude_acesso)
    escreve_campo("Documento de Referência", documento_referencia)
    escreve_campo("Auto de Referência (Data/Hora Serviço)", auto_referencia)
    escreve_campo("Número do CAR", numero_car)
    escreve_campo("Autorizações", autorizacoes)
    escreve_campo("Tipo de Bioma", tipo_bioma)
    escreve_campo("Embargo Imposto na Área", embargo)
    escreve_campo("Área (ha)", str(area))
    escreve_campo("Fontes de Dados", fontes_dados)
    escreve_campo("Escala", escala)
    escreve_campo("Centróide (Latitude)", centroide_lat)
    escreve_campo("Centróide (Longitude)", centroide_lon)
    escreve_campo("Fonte", fonte)

    # Quebra de linha para a análise
    linha_atual -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, linha_atual, "Análise:")
    linha_atual -= 15
    c.setFont("Helvetica", 10)

    # Se a análise for muito longa, você precisará lidar com a quebra de texto;
    # Aqui faremos algo simples
    for linha in analise.split("\n"):
        c.drawString(60, linha_atual, linha)
        linha_atual -= 12

    # Finaliza a página
    c.showPage()
    c.save()

    # Retorna o buffer em posição inicial
    buffer.seek(0)
    return buffer

# --------------------------------------------
# Formulário RIT com botão "Gerar PDF"
# --------------------------------------------
def formulario_rit():
    st.header("Formulário de Relatório de Informações Técnicas (RIT)")

    # Cabeçalho
    rit_num = st.text_input("RIT Nº")
    data = st.date_input("Data", datetime.date.today())

    # Referência
    st.subheader("Referência")
    opm = st.text_input("OPM")
    municipio = st.text_input("Município")
    tipo_area = st.selectbox("Tipo de Área", ["Urbana", "Rural"])
    endereco = st.text_input("Endereço")
    numeral = st.text_input("Número")
    complemento = st.text_input("Complemento")
    ponto_referencia = st.text_input("Ponto de Referência")
    latitude_acesso = st.text_input("Latitude do Acesso")
    documento_referencia = st.text_input("Documento de Referência")
    auto_referencia = st.text_input("Auto de Referência (Data/Hora Serviço)")
    numero_car = st.text_input("Número do CAR")
    autorizacoes = st.text_input("Autorizações")
    tipo_bioma = st.text_input("Tipo de Bioma")
    embargo = st.text_input("Embargo Imposto na Área")
    area = st.number_input("Área em Hectares (ha)", min_value=0.0)

    # Fontes de Dados
    st.subheader("Fontes de Dados")
    fontes_dados = st.text_area("Insira as fontes de dados utilizadas")

    # Localização da Área / Ponto de Acesso
    st.subheader("Localização da Área / Ponto de Acesso")
    escala = st.text_input("Escala")
    centroide_lat = st.text_input("Centróide (Latitude)")
    centroide_lon = st.text_input("Centróide (Longitude)")
    fonte = st.text_input("Fonte")

    # Análise
    st.subheader("Análise")
    analise = st.text_area("Insira sua análise")

    # Em vez de "Enviar", criamos um botão "Gerar PDF"
    if st.button("Gerar PDF"):
        # Gera o PDF com os dados do formulário
        pdf_buffer = gerar_pdf_rit(
            rit_num, data, opm, municipio, tipo_area, endereco, numeral, 
            complemento, ponto_referencia, latitude_acesso, documento_referencia, 
            auto_referencia, numero_car, autorizacoes, tipo_bioma, embargo, area, 
            fontes_dados, escala, centroide_lat, centroide_lon, fonte, analise
        )
        # Exibe um botão para download do PDF
        st.download_button(
            label="Baixar PDF",
            data=pdf_buffer,
            file_name="rit.pdf",
            mime="application/pdf"
        )
        st.success("PDF gerado com sucesso!")

# --------------------------------------------
# Exemplo de main()
# --------------------------------------------
def main():
    st.sidebar.title("Navegação")
    opcao = st.sidebar.radio("Escolha uma opção:", ["RIT"])

    if opcao == "RIT":
        formulario_rit()

if __name__ == "__main__":
    main()
