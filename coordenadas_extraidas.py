import streamlit as st
import zipfile
import xml.etree.ElementTree as ET
import re
import folium
from simplekml import Kml
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import datetime
import base64

# Importações específicas do ReportLab
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors

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

# ============================================
# Função para gerar o PDF do RIT
# ============================================
def gerar_pdf_rit(
    rit_num, data, opm, municipio, tipo_area, endereco, numeral, complemento, 
    bairro, ponto_referencia, latitude, longitude, documento_referencia, auto_referencia, 
    tcra, numero_car, autorizacoes, tipo_bioma, embargo, area, fontes_dados, 
    escala, centroide_lat, centroide_lon, fonte, analise
):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "Relatório de Informações Técnicas (RIT)")

    c.setFont("Helvetica", 10)
    linha_atual = height - 80

    def escreve_campo(label, valor):
        nonlocal linha_atual
        c.drawString(50, linha_atual, f"{label}: {valor}")
        linha_atual -= 15

    escreve_campo("RIT Nº", rit_num)
    escreve_campo("Data", str(data))
    escreve_campo("OPM", opm)
    escreve_campo("Município", municipio)
    escreve_campo("Tipo de Área", tipo_area)
    escreve_campo("Endereço", endereco)
    escreve_campo("Número", numeral)
    escreve_campo("Complemento", complemento)
    escreve_campo("Bairro", bairro)
    escreve_campo("Ponto de Referência", ponto_referencia)
    escreve_campo("Latitude do Acesso", latitude)
    escreve_campo("Longitude do Acesso", longitude)
    escreve_campo("Documento de Referência", documento_referencia)
    escreve_campo("Auto de Referência", auto_referencia)
    escreve_campo("TCRA", tcra)
    escreve_campo("Número do CAR", numero_car)
    escreve_campo("Autorizações", autorizacoes)
    escreve_campo("Tipo de Bioma", tipo_bioma)
    escreve_campo("Embargo", embargo)
    escreve_campo("Área (ha)", str(area))
    escreve_campo("Fontes de Dados", fontes_dados)
    escreve_campo("Escala", escala)
    escreve_campo("Centróide (Latitude)", centroide_lat)
    escreve_campo("Centróide (Longitude)", centroide_lon)
    escreve_campo("Fonte", fonte)

    linha_atual -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, linha_atual, "Análise:")
    linha_atual -= 15
    c.setFont("Helvetica", 10)

    for linha in analise.split("\n"):
        c.drawString(60, linha_atual, linha)
        linha_atual -= 12

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer

def gerar_pdf_rit_com_layout(
    rit_num, data, opm, municipio, tipo_area, endereco, numeral,
    complemento, bairro, ponto_referencia, latitude, longitude,
    documento_referencia, auto_referencia, tcra, numero_car,
    autorizacoes, tipo_bioma, embargo, area, fontes_dados,
    escala, centroide_lat, centroide_lon, fonte, analise
):
    """
    Gera um PDF em memória usando ReportLab Platypus,
    com cabeçalho, imagem, tabelas e texto formatado.
    """
    # 1) Cria buffer para armazenar o PDF em memória
    buffer = BytesIO()

    # 2) Configura o documento (margens, tamanho da página)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30, leftMargin=30,
        topMargin=50, bottomMargin=30
    )

    # 3) Styles (estilos) para parágrafos
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_title_center = ParagraphStyle(
        name="TitleCenter",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=12,
        leading=14
    )

    # 4) Lista de elementos (parágrafos, tabelas, imagens, etc.)
    elements = []

    # 4.1) Imagem de cabeçalho (LOGO) - Ajuste o caminho e tamanho
    elements.append(Image("Asa_Ambinetal.png", width=60, height=60, hAlign='CENTER'))

    # 4.2) Cabeçalho centralizado (linhas)
    cabecalho_linhas = [
        "SECRETARIA DE SEGURANÇA PÚBLICA",
        "POLÍCIA MILITAR DO ESTADO DE SÃO PAULO",
        "COMANDO DE POLÍCIA AMBIENTAL",
        "5° BATALHÃO DE POLÍCIA AMBIENTAL",
        "3ª COMPANHIA DE POLÍCIA AMBIENTAL"
    ]
    for linha in cabecalho_linhas:
        p = Paragraph(linha, style_title_center)
        elements.append(p)

    elements.append(Spacer(1, 20))

    # 4.3) Tabela de "REFERÊNCIA" - rótulos e valores
    table_data = [
        ["OPM", opm, "Município", municipio],
        ["Tipo de Área", tipo_area, "Endereço", endereco],
        ["Número", numeral, "Complemento", complemento],
        ["Bairro", bairro, "Ponto Ref.", ponto_referencia],
        ["Lat. Acesso", latitude, "Long. Acesso", longitude],
        ["Doc. Referência", documento_referencia, "Auto Referência", auto_referencia],
        ["TCRA (se houver)", tcra, "Nº do CAR", numero_car],
        ["Autorizações", autorizacoes, "Tipo de Bioma", tipo_bioma],
        ["Embargo", embargo, "Área (ha)", str(area)],
        ["Fontes de Dados", fontes_dados, "Escala", escala],
        ["Fonte Localização", fonte, "", ""],
    ]

    col_widths = [80, 150, 80, 150]
    tabela_referencia = Table(table_data, colWidths=col_widths)
    tabela_referencia.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
    ]))

    elements.append(Paragraph("REFERÊNCIA", styles["Heading2"]))
    elements.append(tabela_referencia)
    elements.append(Spacer(1, 20))

    # 4.4) Análise (parágrafo)
    elements.append(Paragraph("<b>Análise:</b>", styles["Heading3"]))
    elements.append(Paragraph(analise.replace("\n", "<br/>"), style_normal))

    # 5) Monta o documento PDF
    doc.build(elements)

    # 6) Retorna o buffer para o Streamlit
    buffer.seek(0)
    return buffer

# ============================================
# Função para o submenu "Análise de Ocorrências"
# ============================================
def analise_ocorrencias():
    st.header("Análise de Ocorrências")
    st.write("Insira os dados da ocorrência para análise:")

    # Exemplo de campos para o formulário de ocorrência
    descricao = st.text_area("Descrição da Ocorrência")
    data_ocorrencia = st.date_input("Data da Ocorrência", datetime.date.today())
    tipo_ocorrencia = st.selectbox("Tipo de Ocorrência", ["Incêndio", "Desmatamento", "Poluição", "Outros"])
    coordenadas = st.text_input("Coordenadas (ex: -23.5505, -46.6333)")

    if st.button("Analisar Ocorrência"):
        st.success("Ocorrência analisada com sucesso!")
        # Aqui você pode adicionar lógica para processar a ocorrência,
        # por exemplo, traçar rotas ou gerar um relatório

# ============================================
# Código do Formulário RIT
# ============================================
def formulario_rit():
    st.header("Formulário de Relatório de Informações Técnicas (RIT)")

    # --- CAMPOS DO FORMULÁRIO ---
    rit_num = st.text_input("RIT Nº")
    data = st.date_input("Data", datetime.date.today())
    opm = st.text_input("OPM")
    municipio = st.text_input("Município")
    tipo_area = st.selectbox("Tipo de Área", ["Urbana", "Rural"])
    endereco = st.text_input("Endereço")
    numeral = st.text_input("Número")
    complemento = st.text_input("Complemento")
    bairro = st.text_input("Bairro")
    ponto_referencia = st.text_input("Ponto de Referência")
    latitude = st.text_input("Latitude do Acesso")
    longitude = st.text_input("Longitude do Acesso")
    documento_referencia = st.text_input("Documento de Referência")
    auto_referencia = st.text_input("Auto de Referência (Data/Hora Serviço)")
    tcra = st.text_input("TCRA, caso houver")
    numero_car = st.text_input("Número do CAR")
    autorizacoes = st.text_input("Autorizações")
    tipo_bioma = st.text_input("Tipo de Bioma")
    embargo = st.text_input("Embargo Imposto na Área")
    area = st.number_input("Área em Hectares (ha)", min_value=0.0)
    fontes_dados = st.text_area("Fontes de Dados")
    escala = st.text_input("Escala")
    centroide_lat = st.text_input("Centróide (Latitude)")
    centroide_lon = st.text_input("Centróide (Longitude)")
    fonte = st.text_input("Fonte")
    analise = st.text_area("Análise")

    # --- BOTÕES PARA Visualizar e Gerar PDF ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Visualizar PDF"):
            pdf_buffer = gerar_pdf_rit_com_layout(
                rit_num, data, opm, municipio, tipo_area, endereco, numeral,
                complemento, bairro, ponto_referencia, latitude, longitude,
                documento_referencia, auto_referencia, tcra, numero_car,
                autorizacoes, tipo_bioma, embargo, area, fontes_dados,
                escala, centroide_lat, centroide_lon, fonte, analise
            )
            base64_pdf = base64.b64encode(pdf_buffer.read()).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="900" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
            pdf_buffer.seek(0)
    with col2:
        if st.button("Gerar PDF"):
            pdf_buffer = gerar_pdf_rit_com_layout(
                rit_num, data, opm, municipio, tipo_area, endereco, numeral,
                complemento, bairro, ponto_referencia, latitude, longitude,
                documento_referencia, auto_referencia, tcra, numero_car,
                autorizacoes, tipo_bioma, embargo, area, fontes_dados,
                escala, centroide_lat, centroide_lon, fonte, analise
            )
            st.download_button(
                label="Baixar PDF",
                data=pdf_buffer,
                file_name="rit.pdf",
                mime="application/pdf"
            )
            st.success("PDF gerado com sucesso!")

# ============================================
# Função principal com navegação no sidebar
# ============================================
def main():
    st.sidebar.title("Navegação")
    opcao = st.sidebar.radio("Escolha uma opção:", ["Extrator", "RIT", "Análise de Ocorrências"])

    if opcao == "Extrator":
        extrator()
    elif opcao == "RIT":
        formulario_rit()
    elif opcao == "Análise de Ocorrências":
        analise_ocorrencias()

if __name__ == "__main__":
    main()
