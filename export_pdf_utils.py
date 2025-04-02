from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY,TA_LEFT

from PIL import Image as PILImage
import markdown
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import io
import plotly.io as pio
import  numpy as np
from bs4 import BeautifulSoup
def save_plots_in_PDF(figures):
    pdf_filename = "multiple_plots.pdf"
    with PdfPages(pdf_filename) as pdf:
        for fig in figures:
            fig.update_layout(width=1000, height=800)
            # Convert Plotly figure to image
            img_bytes = pio.to_image(fig, format="jpg")
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            # Save image to PDF
            img_array = np.array(img)
            print(img.size)
            plt.figure(figsize=(20, 16))
            plt.imshow(img_array)
            plt.axis("off")
            pdf.savefig(bbox_inches='tight')
            # img.show()
            img.close()

    print(f"All figures saved in {pdf_filename}")

def create_markdown_styles():
    """Create custom styles for different Markdown elements."""
    styles = getSampleStyleSheet()

    # Heading Styles
    h2_style = ParagraphStyle(
    "HeadingStyle",
    parent=styles["Heading5"],
    fontName="Helvetica-Bold",
    fontSize=11,
    alignment=TA_LEFT,
    spaceAfter=10
)

    h1_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        alignment=TA_LEFT,
        spaceAfter=10
    )


    # Paragraph Style
    paragraph_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontSize=9,
        textColor='black',
        alignment=TA_LEFT,
        leading=14
    )


    # List Style
    list_style = ParagraphStyle(
        'OrderedLists',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=15,
        spaceBefore=6,
        spaceAfter=6
    )

    # Styles for inline formatting
    bold_style = ParagraphStyle(
        'Bold',
        parent=paragraph_style,
        fontName='Helvetica-Bold'
    )

    italic_style = ParagraphStyle(
        'Italic',
        parent=paragraph_style,
        fontName='Helvetica-Oblique'
    )

    return {
        'h1': h1_style,
        'h2': h2_style,
        'h3': h2_style,
        'p': paragraph_style,
        'li': list_style,
        'bold': bold_style,
        'italic': italic_style
    }


class AnalysisContent:
    heading = ""
    sub_heading = ""
    figure = None
    paragraph = ""



# Styles for PDF
styles = getSampleStyleSheet()

heading_style = ParagraphStyle(
    "HeadingStyle",
    parent=styles["Heading1"],
    fontName="Helvetica-Bold",
    fontSize=18,
    alignment=TA_LEFT,
    spaceAfter=10
)
sub_heading_style = ParagraphStyle(
    "HeadingStyle",
    parent=styles["Heading5"],
    fontName="Helvetica-Bold",
    fontSize=11,
    alignment=TA_LEFT,
    spaceAfter=10
)

paragraph_style = ParagraphStyle(
    "ParagraphStyle",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=8,
    alignment=TA_JUSTIFY,
    leading=16  # Line spacing
)
def create_pdf(session_analysis,content_to_write, output_filename):
    # Create a canvas object
    doc = SimpleDocTemplate(output_filename, pagesize=letter)
    flowable = []


    # Patient Details
    flowable.append(Paragraph(content_to_write[0].heading,heading_style))
    flowable.append(Paragraph(content_to_write[0].sub_heading,sub_heading_style))
    html_content = markdown.markdown(content_to_write[0].paragraph, extensions=['extra'])
    flowable.append(Paragraph(html_content,paragraph_style))

    #  Session analysis
    flowable.append(Paragraph(session_analysis.sub_heading,sub_heading_style))
    html_content = markdown.markdown(session_analysis.paragraph, extensions=['extra'])
    # flowable.append(Paragraph(html_content,paragraph_style))

    soup = BeautifulSoup(html_content, 'html.parser')
    # Create PDF document
    # Create styles
    print(html_content)
    styles = create_markdown_styles()
    # Process HTML elements

    for element in soup.find_all(['h1', 'h2','h3','h4','h5', 'ul', 'ol',]):
        if element.name in ['h1','h2','h3','h4','h5']:
            # Headings
            flowable.append(Paragraph(element.get_text(), styles['h1']))
        # elif element.name == 'strong':
        #     flowable.append(Paragraph(text, sub_heading_style))
        elif element.name in ['ul', 'ol']:
            for li in element.find_all('li'):
                text = li.get_text()
                # Use bullet or number based on list type
                if li and li.find('strong'):
                    flowable.append(Paragraph(li.find('strong').get_text(), sub_heading_style))
                # if li and li.find('p'):
                #     flowable.append(Paragraph(text, styles['li']))
                if element.name == 'ul':
                    flowable.append(Paragraph('• ' + text, styles['li']))
                else:
                    flowable.append(Paragraph(f"{li.get_text()}", styles['li']))

        # Add some spacing between elements
        flowable.append(Spacer(1, 6))

    flowable.append(PageBreak())

    # ---------------------------------------------------------------
    # Start adding charts info
    # response = content_to_write[0]
    for response in content_to_write[1:]:
        flowable.append(Paragraph(response.heading, heading_style))
        # Add sub Heading
        flowable.append(Paragraph(response.sub_heading, sub_heading_style))
        fig = response.figure
        if fig is not None:
            fig.update_layout(width=1000, height=600)
            img_bytes = pio.to_image(fig, format="jpg")
            img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
            img.save("temp.png")
            # Convert Plotly figure to image
            image_path = "temp.png"  # Change this to your image path
            pil_image = PILImage.open(image_path)
            image_width, image_height = pil_image.size
            # Resize Image (if necessary)
            max_width = 450  # Adjust width for better fitting
            aspect_ratio = image_height / image_width
            image = Image(image_path, width=max_width, height=max_width * aspect_ratio)
            # Add Image with Some Space
            flowable.append(Spacer(1, 10))
            flowable.append(image)
            flowable.append(Spacer(1, 10))
        # Add Paragraph
        html_content = markdown.markdown(response.paragraph)
        flowable.append((Paragraph(html_content, paragraph_style)))
        # Page break
        flowable.append(PageBreak())

    # Build the PDF
    doc.build(flowable)
    print(f"PDF generated successfully: {output_filename}")
    content_to_write.clear()
