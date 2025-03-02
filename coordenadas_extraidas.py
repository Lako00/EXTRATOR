# Bibliotecas padrão do Python
import base64
import datetime
from datetime import datetime as dt
import locale
import re
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO

# Bibliotecas de terceiros
import folium
from PIL import Image, ImageEnhance
from reportlab.lib import colors
from reportlab.lib.colors import black, gray, lightgrey
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as PlatypusImage,
)
from simplekml import Kml
import streamlit as st

styles = getSampleStyleSheet()

# ==========================================
# Código do Extrator
# =======================================================================================================================================================================

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

# Função para converter coordenadas no formato 123456,78 para -12°34'56,78"
def converter_coordenada(coord):
    try:
        # Remove vírgulas e converte para float
        coord = float(coord.replace(",", "."))
        # Separa graus, minutos e segundos
        graus = int(coord // 10000)
        minutos = int((coord % 10000) // 100)
        segundos = coord % 100
        return f"-{graus}°{minutos:02d}'{segundos:.2f}\""
    except Exception as e:
        return "Formato inválido"

# Gerenciamento de estado para o extrator
if 'coordinates' not in st.session_state:
    st.session_state.coordinates = []

def adicionar_coordenadas_manual(texto):
    linhas = texto.strip().split("\n")
    erros = []
    for linha in linhas:
        partes = linha.strip().split()
        if len(partes) < 2:
            erros.append(f"Formato inválido na linha: {linha}")
            continue
        try:
            lat_gms, lon_gms = partes[:2]
            lat_decimal = gms_to_decimal(lat_gms)
            lon_decimal = gms_to_decimal(lon_gms)
            st.session_state.coordinates.append((lat_decimal, lon_decimal))
        except Exception as e:
            erros.append(f"Erro na linha: {linha} - {e}")
    return erros

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
        st.error("Nenhuma coordenada para exportação.")
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
        coordenadas_extraidas = []
        for polygon in root.findall(".//kml:Polygon", ns):
            for outer in polygon.findall(".//kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
                coords = outer.text.strip().split()
                for coord in coords:
                    lon, lat, _ = coord.split(",")
                    coordenadas_extraidas.append((float(lat), float(lon)))
        coordenadas_extraidas.pop()
        st.session_state.coordinates = coordenadas_extraidas
        return "Coordenadas extraídas com sucesso!"
    except Exception as e:
        return f"Erro ao carregar o arquivo KML/KMZ: {e}"

# Função para o submenu do Extrator
def extrator():
    st.header("Extrator de Coordenadas KML/KMZ")
    operacao = st.radio("Escolha a operação:", ["Inserção Manual", "Carregar Arquivo", "Gerar Polígono", "Exportar KMZ", "Limpar Coordenadas"])
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

# ===========================================
# Função para o submenu "Análise de Ocorrências"
# =========================================

def decimal_para_gms(valor):
    graus = int(valor)
    minutos = int((abs(valor) - abs(graus)) * 60)
    segundos = (abs(valor) - abs(graus) - minutos / 60) * 3600
    return f"{graus}°{minutos:02d}'{segundos:.2f}\""

municipios = [
    "ÁGUAS DE SANTA BÁRBARA", "ALAMBARI", "ALUMÍNIO", "ANGATUBA", "ANHEMBI", 
    "APIAÍ", "ARAÇARIGUAMA", "ARAÇOIABA DA SERRA", "ARANDU", "AREIÓPOLIS", "AVARÉ",
    "BARÃO DE ANTONINA", "BARRA DO CHAPÉU", "BOFETE", "BOITUVA", "BOM SUCESSO DE ITARARÉ",
    "BOTUCATU", "BURI", "CAMPINA DO MONTE ALEGRE", "CAPÃO BONITO", "CAPELA DO ALTO", 
    "CERQUEIRA CÉSAR", "CERQUILHO", "CESÁRIO LANGE", "CONCHAS", "CORONEL MACEDO", 
    "FARTURA", "GUAPIARA", "GUAREÍ", "IARAS", "IBIÚNA", "IPERÓ", "ITABERÁ", "ITAI", 
    "ITAOCA", "ITAPETININGA", "ITAPEVA", "ITAPIRAPUÃ PAULISTA", "ITAPORANGA", 
    "ITARARÉ", "ITATINGA", "ITU", "JUMIRIM", "LARANJAL PAULISTA", "MAIRINQUE", 
    "MANDURI", "NOVA CAMPINA", "PARANAPANEMA", "PARDINHO", "PEREIRAS", "PIEDADE", 
    "PILAR DO SUL", "PIRAJU", "PORANGABA", "PORTO FELIZ", "PRATÂNIA", "QUADRA", 
    "RIBEIRA", "RIBEIRÃO BRANCO", "RIBEIRÃO GRANDE", "RIVERSUL", "SALTO DE PIRAPORA", 
    "SÃO MANUEL", "SÃO MIGUEL ARCANJO", "SÃO ROQUE", "SARAPUÍ", "SARUTAIA", 
    "SOROCABA", "TAGUAÍ", "TAPIRAÍ", "TAQUARITUBA", "TAQUARIVAI", "TATUÍ", 
    "TEJUPÁ", "TIETÊ", "TORRE DE PEDRA", "VOTORANTIM", "SÃO ROQUE", "SALTO"
]
bases_dados = ["WEBAIA", "PAMBGEO", "SIGAM", "DATAGEO", "SINESP-BRASIL MAIS", "GOOGLE EARTH", "EAMBIENTE", "SISTEMA DOF LEGADO", "SISTEMA DOF +", "MAP BIOMAS ALERTA"]
biomas = {"Mata Atlântica": ["Floresta Ombrófila Mista", "Floresta Estacional"], "Cerrado": ["Cerrado Sensu Stricto", "Campo Rupestre"]}
estagios_sucessionais = ["Pioneiro", "Inicial", "Médio", "Avançado"]
anos_inventario = ["2000", "2010", "2020"]
policiais = ["1° SGT PM 130896-3 SILVA", "CB PM CLAUDIO", "CB PM BRISOLA", "CB PM ALVES", "CB PM MASAYOSHI"]

def adicionar_cabecalho_rodape(canvas, doc):
    """
    Adiciona um cabeçalho e um rodapé ao PDF.
    """
    canvas.saveState()

    # Dimensões da página A4
    largura_pagina, altura_pagina = A4

    # =================== CABEÇALHO ===================
    # Imagem à esquerda
    try:
        imagem_esquerda = ImageReader("Brasão_do_estado_de_São_Paulo.png")
        canvas.drawImage(imagem_esquerda, 50, altura_pagina - 150, width=75, height=75, mask='auto')
    except Exception as e:
        st.error(f"Erro ao carregar imagem esquerda: {e}")

    # Imagem à direita
    try:
        imagem_direita = ImageReader("pmesp.png")
        canvas.drawImage(imagem_direita, largura_pagina - 125, altura_pagina - 150, width=75, height=75, mask='auto')
    except Exception as e:
        st.error(f"Erro ao carregar imagem direita: {e}")

    # Texto do cabeçalho
    styles = getSampleStyleSheet()
    estilo_cabecalho = ParagraphStyle(
        name="Cabecalho",
        parent=styles["Normal"],
        fontSize=10,
        alignment=1,  # Centralizado
        spaceAfter=6,
        textColor=black
    )

    # Linhas do cabeçalho
    linhas_cabecalho = [
        "SECRETARIA DA SEGURANÇA PÚBLICA",
        "POLÍCIA MILITAR DO ESTADO DE SÃO PAULO",
        "COMANDO DE POLICIAMENTO AMBIENTAL",
        "5° BPAMB / 3ª CIA / SEÇÃO TÉCNICA"
    ]

    # Posiciona o texto no centro
    y = altura_pagina - 80
    for linha in linhas_cabecalho:
        p = Paragraph(linha, estilo_cabecalho)
        p.wrapOn(canvas, largura_pagina - 200, 50)
        p.drawOn(canvas, 100, y)
        y -= 15

    # Adiciona um espaçamento fixo após o cabeçalho
    canvas.translate(0, -2 * cm)  # Ajuste o valor conforme necessário

    # =================== RODAPÉ ===================
    # Texto do rodapé
    estilo_rodape = ParagraphStyle(
        name="Rodape",
        parent=styles["Normal"],
        fontSize=6,
        alignment=1,  # Centralizado
        spaceBefore=10,
        textColor=black
    )

    texto_rodape = "“Nós, Policiais Militares, sob a proteção de Deus, estamos compromissados com a Defesa da Vida, da Integridade Física e da Dignidade da Pessoa Humana”"
    p_rodape = Paragraph(texto_rodape, estilo_rodape)
    p_rodape.wrapOn(canvas, largura_pagina - 100, 50)
    p_rodape.drawOn(canvas, 50, 30)

    canvas.restoreState()

def adicionar_marca_dagua(canvas, doc):
    """
    Adiciona uma imagem como marca d'água no PDF, com transparência ajustada.
    """
    canvas.saveState()
    
    # Carrega a imagem
    try:
        imagem = Image.open("asa_ambiental.png")  # Carrega a imagem da pasta
        
        # Ajusta a transparência (opacidade) da imagem
        alpha = 0.3  # Valor entre 0 (totalmente transparente) e 1 (totalmente opaco)
        imagem = imagem.convert("RGBA")  # Garante que a imagem tenha canal alfa
        dados = imagem.getdata()  # Obtém os dados da imagem

        # Aplica a transparência
        novos_dados = []
        for item in dados:
            # Mantém os canais RGB e ajusta o canal alfa (transparência)
            novos_dados.append((item[0], item[1], item[2], int(item[3] * alpha)))

        imagem.putdata(novos_dados)  # Aplica os novos dados à imagem
        imagem = ImageReader(imagem)  # Converte para um formato que o ReportLab entenda
    except Exception as e:
        st.error(f"Erro ao carregar a imagem: {e}")
        return

    # Dimensões da página A4
    largura_pagina, altura_pagina = A4

    # Tamanho da imagem (ajuste conforme necessário)
    largura_imagem = 400  # Largura da imagem em pixels
    altura_imagem = 200   # Altura da imagem em pixels

    # Posiciona a imagem no centro da página
    x = (largura_pagina - largura_imagem) / 2
    y = (altura_pagina - altura_imagem) / 2

    # Desenha a imagem no PDF
    canvas.drawImage(imagem, x, y, width=largura_imagem, height=altura_imagem, mask='auto')

    canvas.restoreState()

def adicionar_cabecalho_rodape_e_marca_dagua(canvas, doc):
    """
    Adiciona cabeçalho, rodapé e marca d'água ao PDF.
    """
    # Adiciona o cabeçalho e o rodapé
    adicionar_cabecalho_rodape(canvas, doc)

    # Adiciona a marca d'água (imagem clareada)
    adicionar_marca_dagua(canvas, doc)

def adicionar_imagens_ao_pdf(imagem1, data_imagem1, imagem2, data_imagem2):
    if imagem1 and imagem2:
        imagem1_redimensionada = redimensionar_imagem(imagem1)
        imagem2_redimensionada = redimensionar_imagem(imagem2)
        buffer1 = BytesIO()
        imagem1_redimensionada.save(buffer1, format="PNG")
        buffer1.seek(0)
        buffer2 = BytesIO()
        imagem2_redimensionada.save(buffer2, format="PNG")
        buffer2.seek(0)
        imagem1_elemento = PlatypusImage(buffer1, width=150, height=150)
        imagem2_elemento = PlatypusImage(buffer2, width=150, height=150)
        dados_tabela_imagens = [
            [f"Data: {data_imagem1}", "", f"Data: {data_imagem2}"],
            [imagem1_elemento, "", imagem2_elemento]
        ]
        tabela_imagens = Table(dados_tabela_imagens, colWidths=[150, 90, 150], rowHeights=[20, 150])
        estilo_tabela = TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('SPACEAFTER', (0, 0), (-1, -1), 10),
        ])
        tabela_imagens.setStyle(estilo_tabela)
        return tabela_imagens
    return None

# Função para redimensionar imagens
def redimensionar_imagem(imagem, tamanho=(150, 150)):
    """
    Redimensiona uma imagem para o tamanho especificado.
    """
    return imagem.resize(tamanho)

# Função para criar a tabela de conclusão
def criar_tabela_conclusao(dados, colWidths):
    """
    Cria a tabela de conclusão com estilo personalizado.
    """
    tabela = Table(dados, colWidths=colWidths)
    estilo_tabela = TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),  # Borda apenas abaixo do título
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Centraliza o título "Conclusão"
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),  # Alinha o texto da conclusão à esquerda
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Alinhamento vertical no topo
        ('WORDWRAP', (0, 0), (-1, -1), True),  # Quebra de texto automática
        ('SPLITLONGWORDS', (0, 0), (-1, -1), True),  # Quebra de palavras longas
    ])
    tabela.setStyle(estilo_tabela)
    return tabela

# Estilo para a conclusão (texto justificado)
estilo_conclusao = ParagraphStyle(
    name="Conclusao",
    parent=styles["Normal"],  # use 'styles' se você o definiu como styles
    fontSize=12,
    alignment=4,  # justificado
    leading=14
)

def criar_tabela(dados, colWidths):
    tabela = Table(dados, colWidths=colWidths)
    estilo_tabela = TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Bordas pretas
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alinhamento à esquerda
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Alinhamento vertical no topo
        ('WORDWRAP', (0, 0), (-1, -1), True),  # Quebra de texto automática
        ('SPLITLONGWORDS', (0, 0), (-1, -1), True),  # Quebra de palavras longas
    ])
    tabela.setStyle(estilo_tabela)
    return tabela

# Função para gerar o PDF
def gerar_pdf(relatorio, filename="relatorio_analise.pdf"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    # Estilo personalizado para o título
    estilo_titulo = ParagraphStyle(
        name="Titulo",
        parent=styles["Title"],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.black
    )

    # Estilo personalizado para o corpo do texto
    estilo_corpo = ParagraphStyle(
        name="Corpo",
        parent=styles["Normal"],
        fontSize=12,
        spaceAfter=10,
        textColor=colors.black
    )

    # Estilo para o responsável (alinhado à direita)
    estilo_responsavel = ParagraphStyle(
        name="Responsavel",
        parent=styles["Normal"],
        fontSize=12,
        alignment=TA_RIGHT,  # Alinhado à direita
        spaceBefore=20,
        textColor=colors.black
    )

    elementos = []

    # Adiciona um espaço no início do conteúdo para evitar sobreposição
    elementos.append(Spacer(1, 2 * cm))  # 2 cm de espaço (ajuste conforme necessário)

    # Adiciona o conteúdo do relatório
    elementos.append(Paragraph("Relatório de Análise de Ocorrências", styles["Title"]))
    elementos.append(Spacer(1, 12))  # Espaço entre o título e o conteúdo

    # Dados para a primeira tabela
    dados_tabela1 = [
        ["Número do Relatório", relatorio.get("numero_relatorio", "N/A")],
        ["Data do Relatório", relatorio.get("data_relatorio", "N/A")],
        ["Período de Análise (Início)", relatorio.get("periodo_inicio", "N/A")],  # Nova linha
        ["Período de Análise (Fim)", relatorio.get("periodo_fim", "N/A")],  # Nova linha
        ["Município", relatorio.get("municipio", "N/A")],
        ["Endereço", relatorio.get("endereco", "N/A")],
        ["Latitude", relatorio.get('lat_gms', 'N/A')],
        ["Longitude", relatorio.get('lon_gms', 'N/A')],
        ["Número WEBAIA", relatorio.get("numero_webaia", "N/A")],
    ]

    # Dados para a segunda tabela (demais informações)
    dados_tabela2 = [
        ["Tipo de Área", relatorio.get("tipo_area", "N/A")],
        ["Bioma", relatorio.get("bioma", "N/A")],
        ["Tipo de Vegetação", relatorio.get("tipo_vegetacao", "N/A")],
        ["Estágio Sucessional", relatorio.get("estagio_sucessional", "N/A")],
        ["Ano do Inventário", relatorio.get("ano_inventario", "N/A")],
        ["Vegetação no Inventário", relatorio.get("vegetacao_inventario", "N/A")],
        ["Fiscalizações Anteriores", relatorio.get("fiscalizacao_info", "Nenhuma")],
        ["Licenças", relatorio.get("descricao_licenca", "Nenhuma")],
        ["Bases de Dados Consultadas", relatorio.get("bases_dados", "Nenhuma")],  # Nova linha
    ]

    # Adiciona as tabelas ao PDF
    elementos.append(criar_tabela(dados_tabela1, [200, 300]))  # Primeira tabela
    elementos.append(Spacer(1, 20))  # Espaço entre as tabelas
    elementos.append(criar_tabela(dados_tabela2, [200, 300]))  # Segunda tabela
    elementos.append(Spacer(1, 20))  # Espaço entre as tabelas

    # Estilo para a conclusão (texto justificado)
    estilo_conclusao = ParagraphStyle(
        name="Conclusao",
        parent=styles["Normal"],
        fontSize=12,
        alignment=4,  # 4 = Justificado
        leading=14,   # Espaçamento entre linhas
        wordWrap=True,  # Quebra de texto automática
        splitLongWords=True,  # Quebra de palavras longas
    )
    
    # Adiciona as imagens ao PDF (antes da conclusão)
    if relatorio.get("imagem1") and relatorio.get("imagem2"):
        # Adiciona um espaçamento antes da tabela
        elementos.append(Spacer(1, 20))  # 20 pontos de espaçamento

        # Adiciona a tabela de imagens e datas
        tabela_imagens = adicionar_imagens_ao_pdf(
            relatorio["imagem1"], relatorio["data_imagem1"],
            relatorio["imagem2"], relatorio["data_imagem2"]
        )
        elementos.append(tabela_imagens)

    # Adiciona um espaçamento após a tabela
    elementos.append(Spacer(1, 20))  # 20 pontos de espaçamento

    # Adiciona a conclusão ao PDF
    conclusao_texto = ""
    if relatorio.get("conclusao_fiscalizacao", False):
        conclusao_texto = "Diante das informações apresentadas, sugiro o envio de equipe para fiscalização 'in loco' com fulcro da constatação de crimes ambientais, para eventual adoção de medidas penais e administrativas em caso de confirmação das informações descritas neste termo."
    elif relatorio.get("conclusao_encerramento", False):
        conclusao_texto = "Diante das informações apresentadas, sugiro o encerramento e arquivamento da ocorrência, até nova solicitação."
    else:
        conclusao_texto = "Nenhuma conclusão foi selecionada."

    elementos.append(Paragraph("<b>Conclusão</b>", styles["Heading2"]))  # Título da conclusão
    elementos.append(Spacer(1, 10))  # Espaço antes do texto
    elementos.append(Paragraph(conclusao_texto, estilo_conclusao))  # Texto justificado
    elementos.append(Spacer(1, 20))  # Espaço após a conclusão

    # Adiciona o responsável centralizado à direita
    responsavel = f"Responsável: {relatorio.get('responsavel', 'N/A')}"
    elementos.append(Spacer(1, 20))  # Espaço antes do responsável
    elementos.append(Paragraph(responsavel, estilo_responsavel))

    # Gera o PDF com cabeçalho, rodapé e marca d'água
    doc.build(elementos, onFirstPage=adicionar_cabecalho_rodape_e_marca_dagua, onLaterPages=adicionar_cabecalho_rodape_e_marca_dagua)
    buffer.seek(0)
    return buffer

def validar_data(data_str, formato="%d/%m/%Y"):
    try:
        return dt.strptime(data_str, formato).date()
    except ValueError:
        return None

def analise_ocorrencias():
    st.header("Análise de Ocorrências")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        numero_relatorio = st.text_input("Número do Relatório")
    
    with col2:
        data_relatorio_str = st.text_input("Data do Relatório (dd/mm/aaaa)", value=datetime.date.today().strftime("%d/%m/%Y"))
        data_relatorio = validar_data(data_relatorio_str)
        if data_relatorio is None:
            st.error("Formato de data inválido. Use dd/mm/aaaa.")
        else:
            data_relatorio_formatada = data_relatorio.strftime("%d/%m/%Y")
    
    with col3:
        periodo_inicio_str = st.text_input("Período de Análise - Início (dd/mm/aaaa)", value=datetime.date.today().strftime("%d/%m/%Y"))
        periodo_inicio = validar_data(periodo_inicio_str)
        if periodo_inicio is None:
            st.error("Formato de data inválido. Use dd/mm/aaaa.")
    
    with col4:
        periodo_fim_str = st.text_input("Período de Análise - Fim (dd/mm/aaaa)", value=datetime.date.today().strftime("%d/%m/%Y"))
        periodo_fim = validar_data(periodo_fim_str)
        if periodo_fim is None:
            st.error("Formato de data inválido. Use dd/mm/aaaa.")
    
    
    st.markdown("### 📌 Dados da área de interesse")
    municipio = st.selectbox("Município", municipios)
    endereco = st.text_input("Endereço")
    col1, col2 = st.columns(2)
    with col1:
        latitude = st.text_input("Latitude (ex: 123456,78)")
        lat_gms = converter_coordenada(latitude) if latitude else "N/A"
        st.text(f"Formato GMS: {lat_gms}")
    with col2:
        longitude = st.text_input("Longitude (ex: 123456,78)")
        lon_gms = converter_coordenada(longitude) if longitude else "N/A"
        st.text(f"Formato GMS: {lon_gms}")
    numero_webaia = st.text_input("Número da WEBAIA")

    st.markdown("### 🔎 Consulta Base de Dados")
    selecionados = {}
    for base in bases_dados:
        selecionados[base] = st.checkbox(base)
    if selecionados.get("Outros"):
        info_outros = st.text_area("Descreva outras bases de dados utilizadas")

    # Título do formulário
    st.markdown("### 📷 Imagens")

    # Opções para o menu suspenso
    fontes_imagens = ["Google Earth", "SINESP MAIS", "Sentinel", "Outros"]

    # Menu suspenso para escolher a fonte das imagens
    fonte_escolhida = st.selectbox("Fonte das Imagens", fontes_imagens)

     # Título dinâmico com a fonte escolhida
    st.title(f"IMAGENS: {fonte_escolhida}")

    # Caixa para carregar Imagem 1
    st.markdown("### 📷 Imagem 1")
    imagem1 = st.file_uploader("Carregar Imagem 1", type=["png", "jpg", "jpeg"])
    data_imagem1 = st.date_input("Data da Imagem 1", datetime.date.today())

    # Exibir Imagem 1, se carregada
    if imagem1 is not None:
        imagem1_carregada = Image.open(imagem1)
        st.image(imagem1_carregada, caption="Imagem 1 Carregada", width=300)

    # Caixa para carregar Imagem 2
    st.markdown("### 📷 Imagem 2")
    imagem2 = st.file_uploader("Carregar Imagem 2", type=["png", "jpg", "jpeg"])
    data_imagem2 = st.date_input("Data da Imagem 2", datetime.date.today())

    # Exibir Imagem 2, se carregada
    if imagem2 is not None:
        imagem2_carregada = Image.open(imagem2)
        st.image(imagem2_carregada, caption="Imagem 2 Carregada", width=300)

    # Formate as datas para o formato desejado (dd/mm/aaaa)
    data_imagem1_formatada = data_imagem1.strftime("%d/%m/%Y")
    data_imagem2_formatada = data_imagem2.strftime("%d/%m/%Y")


    st.markdown("### 📋 Análise")
    tipo_area = st.selectbox("Área", ["Área de Preservação Permanente (APP)", "Área Comum"])
    bioma = st.selectbox("Bioma", list(biomas.keys()))
    tipo_vegetacao = st.selectbox("Tipo de Vegetação", biomas[bioma])
    estagio_sucessional = st.selectbox("Estágio Sucessional da Vegetação", estagios_sucessionais)
    inventario_check = st.checkbox("Inventário Florestal")
    if inventario_check:
        ano_inventario = st.selectbox("Ano do Inventário", anos_inventario)
        vegetacao_inventario = st.selectbox("Tipo de Vegetação no Inventário", biomas[bioma])
    fiscalizacao_check = st.checkbox("Existência de Fiscalizações do PAMB Anteriormente")
    if fiscalizacao_check:
        fiscalizacao_info = st.text_area("Detalhes da fiscalização anterior (máx 1000 caracteres)", max_chars=1000)
    else:
        fiscalizacao_info = "Nenhuma"

    licenca_check = st.checkbox("Licenças")
    nao_ha_licenca = st.checkbox("Não há licença")  # Novo checkbox
    if not nao_ha_licenca:
        descricao_licenca = st.text_area("Descreva as licenças encontradas")
    else:
        descricao_licenca = "Nenhuma"

    st.markdown("### 🔍 Conclusão")
    conclusao_fiscalizacao = st.checkbox(
        "Diante das informações apresentadas, sugiro o envio de equipe para fiscalização 'in loco' com fulcro da constatação de crimes ambientais, para eventual adoção de medidas penais e administrativas em caso de confirmação das informações descritas neste termo."
    )
    conclusao_encerramento = st.checkbox(
        "Diante das informações apresentadas, sugiro o encerramento e arquivamento da ocorrência, até nova solicitação."
    )
    responsavel = st.selectbox("Responsável pela análise", policiais)


    if st.button("Visualizar Relatório"):
        relatorio = {
            "numero_relatorio": numero_relatorio,
            "data_relatorio": data_relatorio_formatada,
            "municipio": municipio,
            "endereco": endereco,
            "latitude": latitude,
            "longitude": longitude,
            "lat_gms": lat_gms,
            "lon_gms": lon_gms,
            "numero_webaia": numero_webaia,
            "tipo_area": tipo_area,
            "bioma": bioma,
            "tipo_vegetacao": tipo_vegetacao,
            "estagio_sucessional": estagio_sucessional,
            "ano_inventario": ano_inventario if inventario_check else "N/A",
            "vegetacao_inventario": vegetacao_inventario if inventario_check else "N/A",
            "fiscalizacao_info": fiscalizacao_info if fiscalizacao_check else "Nenhuma",
            "descricao_licenca": descricao_licenca if licenca_check else "Nenhuma",
            "conclusao_fiscalizacao": conclusao_fiscalizacao,
            "conclusao_encerramento": conclusao_encerramento,
            "responsavel": responsavel,
            "bases_dados": ", ".join([base for base, selecionado in selecionados.items() if selecionado]),
            "imagem1": Image.open(imagem1) if imagem1 else None,
            "data_imagem1": data_imagem1_formatada,  # Data formatada
            "imagem2": Image.open(imagem2) if imagem2 else None,
            "data_imagem2": data_imagem2_formatada,  # Data formatada
        }

        pdf_buffer = gerar_pdf(relatorio)
        st.success("Relatório gerado com sucesso!")
        base64_pdf = base64.b64encode(pdf_buffer.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="900" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    
    if st.button("Gerar PDF"):
        relatorio = {
            "numero_relatorio": numero_relatorio,
            "data_relatorio": data_relatorio_formatada,  # Usando a data formatada
            "municipio": municipio,
            "endereco": endereco,
            "latitude": latitude,
            "longitude": longitude,
            "lat_gms": lat_gms,
            "lon_gms": lon_gms,
            "numero_webaia": numero_webaia,
            "tipo_area": tipo_area,
            "bioma": bioma,
            "tipo_vegetacao": tipo_vegetacao,
            "estagio_sucessional": estagio_sucessional,
            "ano_inventario": ano_inventario if inventario_check else "N/A",
            "vegetacao_inventario": vegetacao_inventario if inventario_check else "N/A",
            "fiscalizacao_info": fiscalizacao_info if fiscalizacao_check else "Nenhuma",
            "descricao_licenca": descricao_licenca if licenca_check else "Nenhuma",
            "conclusao_fiscalizacao": conclusao_fiscalizacao,
            "conclusao_encerramento": conclusao_encerramento,
            "responsavel": responsavel,
            "bases_dados": ", ".join([base for base, selecionado in selecionados.items() if selecionado]),
            "imagem1": Image.open(imagem1) if imagem1 else None,
            "data_imagem1": data_imagem1_formatada,  # Data formatada
            "imagem2": Image.open(imagem2) if imagem2 else None,
            "data_imagem2": data_imagem2_formatada,  # Data formatada
        }
        pdf_buffer = gerar_pdf(relatorio)
        st.download_button(label="Baixar Relatório em PDF", data=pdf_buffer, file_name="relatorio_analise.pdf", mime="application/pdf")

# ============================================
# Função principal com navegação no sidebar
# ==========================================

def main():
    st.sidebar.title("MENU")
    opcao = st.sidebar.radio("Escolha uma opção:", ["Análise de Ocorrências", "Extrator", "RIT(em desenvolvimento)"])
    if opcao == "Análise de Ocorrências":
        analise_ocorrencias()
    elif opcao == "Extrator":
        extrator()
    elif opcao == "RIT (em desenvolvimento)":
        st.write("Funcionalidade em desenvolvimento...")

if __name__ == "__main__":
    main()
