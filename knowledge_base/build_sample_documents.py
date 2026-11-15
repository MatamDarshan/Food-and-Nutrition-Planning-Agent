"""
knowledge_base/build_sample_documents.py
----------------------------------------
Generates authoritative ICMR-NIN Indian Nutrition Guidelines and
Food Composition reference PDF documents for RAG document indexing.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

DOCS_DIR = Path(__file__).resolve().parent / "nutrition_documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def build_dietary_guidelines_pdf():
    pdf_path = DOCS_DIR / "ICMR_NIN_Dietary_Guidelines_for_Indians.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("DocTitle", parent=styles["Heading1"], fontSize=20, leading=24, textColor=colors.HexColor("#1A365D"), spaceAfter=14)
    heading_style = ParagraphStyle("DocHeading", parent=styles["Heading2"], fontSize=14, leading=18, textColor=colors.HexColor("#2B6CB0"), spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("DocBody", parent=styles["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#2D3748"), spaceAfter=8)
    callout_style = ParagraphStyle("Callout", parent=styles["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#22543D"), backColor=colors.HexColor("#F0FFF4"), borderPadding=8, spaceBefore=6, spaceAfter=8)

    story = []

    # Title & Front Matter
    story.append(Paragraph("ICMR-NIN Dietary Guidelines for Indians", title_style))
    story.append(Paragraph("<b>National Institute of Nutrition (Indian Council of Medical Research), Hyderabad</b>", body_style))
    story.append(Paragraph("<i>Official Reference Manual on Nutritional Requirements, Balanced Diets, and Food Synergy</i>", body_style))
    story.append(Spacer(1, 14))

    # Chapter 1: Millets
    story.append(Paragraph("Chapter 1: Nutri-Cereals and the Nutritional Benefits of Millets", heading_style))
    story.append(Paragraph(
        "Millets (Shree Anna) are traditional nutri-cereals cultivated extensively across India. "
        "They offer profound therapeutic and nutritional advantages over refined grains due to their high concentration of "
        "dietary fiber, essential minerals, vitamins, and bioactive phytochemicals.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>Key Millets & Their Specific Benefits:</b><br/>"
        "• <b>Finger Millet (Ragi / Nachni):</b> Richest plant source of calcium (approx 344 mg per 100g), crucial for bone mineralization, osteoporosis prevention, and maternal health.<br/>"
        "• <b>Pearl Millet (Bajra):</b> Exceptionally rich in iron (approx 8 mg per 100g) and zinc, helping combat nutritional anemia. High in resistant starch and insoluble fiber.<br/>"
        "• <b>Sorghum (Jowar):</b> Contains abundant anthocyanins, tannins, and policosanols that assist in lowering LDL cholesterol and mitigating oxidative stress.<br/>"
        "• <b>Foxtail & Barnyard Millet:</b> Possess low glycemic index (GI < 55), triggering slow glucose release into the bloodstream, making them ideal for diabetes and metabolic management.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>Clinical Impact:</b> Regular consumption of millets reduces postprandial glycemic excursions, improves lipid profiles, "
        "and supplies prebiotic carbohydrates that stimulate beneficial gut microbiota (Bifidobacteria and Lactobacilli).",
        callout_style,
    ))
    story.append(Spacer(1, 10))

    # Chapter 2: Indian Protein Sources
    story.append(Paragraph("Chapter 2: Indian Food Sources of Protein and Amino Acid Complementarity", heading_style))
    story.append(Paragraph(
        "Adequate protein intake is essential for maintaining muscle mass, enzymatic activity, and immune function. "
        "The recommended dietary allowance (RDA) for an Indian adult is 0.83g to 1.0g per kg body weight per day, "
        "increasing to 1.6–2.2g/kg for active athletes or weight-management protocols.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>Top Vegetarian Protein Sources in Indian Diets:</b><br/>"
        "1. <b>Pulses and Legumes:</b> Chickpeas (Chana), Lentils (Dal Tadka, Moong Dal), Kidney Beans (Rajma), and Black Gram (Urad Dal) deliver 20–25g protein per 100g dry weight.<br/>"
        "2. <b>Dairy Products:</b> Paneer (18g/100g), Greek yogurt / Hung Curd (8–10g/100g), and low-fat milk provide high biological value (HBV) protein rich in branched-chain amino acids (BCAAs), particularly leucine.<br/>"
        "3. <b>Soybeans & Besan:</b> Soybean flour (40% protein) and Besan (chickpea flour, 22% protein) are dense plant protein sources.<br/>"
        "4. <b>Sprouted Legumes:</b> Germination increases protein bioavailability, degrades phytates, and enhances vitamin C and B-complex content.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>Top Non-Vegetarian Protein Sources:</b><br/>"
        "• <b>Eggs:</b> A standard egg provides ~6g of complete protein with a Protein Digestibility Corrected Amino Acid Score (PDCAAS) of 1.0.<br/>"
        "• <b>Skinless Chicken Breast:</b> Yields ~25g protein per 100g with low saturated fat.<br/>"
        "• <b>Fish (Rohu, Katla, Pomfret):</b> Excellent source of lean protein (18–20g/100g) along with cardioprotective Omega-3 fatty acids (EPA and DHA).",
        body_style,
    ))
    story.append(Paragraph(
        "<b>The Principle of Cereal-Pulse Synergy:</b> Indian cereals (like rice and wheat) are rich in sulfur-containing amino acids (methionine, cysteine) but deficient in lysine. "
        "Conversely, pulses are rich in lysine but limited in methionine. Combining cereals and pulses in a ratio of <b>4:1 to 5:1</b> "
        "(e.g., Khichdi, Idli-Sambar, Dal-Roti) creates a complete amino acid profile rivaling animal protein.",
        callout_style,
    ))
    story.append(PageBreak())

    # Chapter 3: Dietary Fibre
    story.append(Paragraph("Chapter 3: The Importance of Dietary Fibre in Human Health", heading_style))
    story.append(Paragraph(
        "Dietary fibre constitutes the edible parts of plants that resist enzymatic digestion and absorption in the human small intestine. "
        "ICMR-NIN recommends a minimum daily intake of <b>30g to 40g of dietary fibre</b> for Indian adults (or 14g per 1,000 kcal consumed).",
        body_style,
    ))
    story.append(Paragraph(
        "<b>Soluble vs. Insoluble Fibre:</b><br/>"
        "• <b>Soluble Fibre (Pectins, Gums, Beta-glucans):</b> Dissolves in water forming a viscous gel. Found in oats, barley, apples, guava, and pulses. "
        "It slows carbohydrate digestion, blunts glycemic spikes, and binds to bile acids in the intestine to lower circulating serum LDL cholesterol.<br/>"
        "• <b>Insoluble Fibre (Cellulose, Hemicellulose, Lignin):</b> Does not dissolve in water. Found in whole wheat bran, brown rice, ragi, and vegetable skins. "
        "It attracts water into the stool, adds fecal bulk, accelerates transit time, and prevents diverticulosis and constipation.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>Microbiome & Short-Chain Fatty Acids (SCFAs):</b><br/>"
        "When dietary prebiotic fiber reaches the large intestine, anaerobic colonic bacteria ferment it into short-chain fatty acids (acetate, propionate, and butyrate). "
        "Butyrate serves as the primary energy fuel for colonocytes, maintains gut barrier integrity, suppresses systemic inflammation, and lowers colorectal cancer risks.",
        body_style,
    ))
    story.append(Spacer(1, 10))

    # Chapter 4: Whole Grains vs Refined Grains
    story.append(Paragraph("Chapter 4: Whole Grains versus Refined Grains", heading_style))
    story.append(Paragraph(
        "The anatomical grain kernel consists of three distinct components: "
        "1. <b>The Bran:</b> The hard outer shell containing dietary fiber, B vitamins, iron, copper, zinc, magnesium, and phytochemicals.<br/>"
        "2. <b>The Germ:</b> The nutrient-dense embryo rich in vitamin E, healthy unsaturated fats, B vitamins, and antioxidants.<br/>"
        "3. <b>The Endosperm:</b> The large interior storage tissue consisting primarily of starchy carbohydrates and modest protein.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>Comparison: Whole Wheat / Brown Rice vs. Maida (Refined Flour) / White Polished Rice:</b>",
        body_style,
    ))

    # Table of comparison
    table_data = [
        ["Parameter", "Whole Grain (Atta, Brown Rice, Ragi)", "Refined Grain (Maida, Polished Rice)"],
        ["Anatomy", "Bran, Germ, and Endosperm intact", "Bran and Germ stripped away during milling"],
        ["Fiber Content", "High (8–12g per 100g)", "Very low (1–2g per 100g)"],
        ["Glycemic Index", "Low to Medium (GI 50–65)", "High (GI 70–85) — causes rapid insulin spikes"],
        ["Micronutrients", "Retains natural B-vitamins, iron, magnesium", "Lost in milling; mostly empty calories"],
        ["Satiety Value", "High satiety; promotes prolonged fullness", "Low satiety; stimulates rebound hunger"],
    ]
    t = Table(table_data, colWidths=[110, 190, 190])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "<b>ICMR-NIN Recommendation:</b> At least 50% to 70% of total daily cereal intake should be derived from intact whole grains and millets rather than ultra-processed refined flours.",
        callout_style,
    ))
    story.append(PageBreak())

    # Chapter 5: Essential Micronutrients: Calcium, Iron, and Vitamin B12
    story.append(Paragraph("Chapter 5: Essential Micronutrients: Calcium, Iron, and Vitamin B12", heading_style))
    story.append(Paragraph(
        "Micronutrients are vital organic and inorganic compounds required in small quantities for cellular metabolism, "
        "structural integrity, and enzymatic cofactor functions. ICMR-NIN establishes specific daily dietary allowances for Indians.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>1. Calcium:</b><br/>"
        "• <b>Recommended Dietary Allowance (RDA):</b> 1,000 mg/day for adult men and women, increasing to 1,200 mg/day for postmenopausal women and the elderly.<br/>"
        "• <b>Primary Food Sources:</b> Finger millet (Ragi) provides 344 mg/100g; white sesame seeds (Til) provide ~1,450 mg/100g; cow's milk (120 mg/100ml), paneer (480 mg/100g), and dark green leafy vegetables (curry leaves, amaranth).<br/>"
        "• <b>Absorption Context:</b> Adequate Vitamin D synthesis (via 20–30 minutes of midday sunlight exposure) is mandatory for active intestinal calcium transport. Excessive dietary oxalates (in raw spinach) and phytates can inhibit calcium bioavailability.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>2. Iron:</b><br/>"
        "• <b>Recommended Dietary Allowance (RDA):</b> 19 mg/day for adult men, and 29 mg/day for adult non-pregnant women of reproductive age.<br/>"
        "• <b>Plant Sources (Non-Heme Iron):</b> Pearl millet (Bajra, 8 mg/100g), garden cress seeds (Alivera, 100 mg/100g), green leafy vegetables (Palak, fenugreek/methi), and lentils/chana.<br/>"
        "• <b>Bioavailability Enhancers & Inhibitors:</b> Non-heme iron absorption is enhanced 2- to 3-fold by co-ingesting Vitamin C (citrus fruits, amla, lemon juice). Polyphenols and tannins in tea and coffee strongly inhibit iron absorption and should be avoided for 1 hour before and after meals.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>3. Vitamin B12 (Cobalamin):</b><br/>"
        "• <b>Recommended Dietary Allowance (RDA):</b> 2.2 to 2.5 mcg/day for Indian adults.<br/>"
        "• <b>Biological Role:</b> Essential for red blood cell formation (preventing megaloblastic anemia), neurological integrity (myelin sheath maintenance), and DNA synthesis.<br/>"
        "• <b>Dietary Sources & Vegan Considerations:</b> Vitamin B12 is synthesized exclusively by microorganisms and is absent from unfortified plant foods. In Indian vegetarian diets, dairy products (milk, curd, paneer) are the sole natural dietary source. Non-vegetarians obtain it from eggs, fish, and poultry. Strict vegans and individuals with gastrointestinal malabsorption require fortified foods or oral B12 supplements.",
        body_style,
    ))
    story.append(Spacer(1, 10))

    # Chapter 6: Dietary Fats, Fatty Acid Balance, and Cooking Oils
    story.append(Paragraph("Chapter 6: Dietary Fats, Fatty Acid Balance, and Cooking Oils", heading_style))
    story.append(Paragraph(
        "Dietary fats are an essential macronutrient providing concentrated energy (9 kcal/g), aiding the absorption of fat-soluble "
        "vitamins (A, D, E, K), and supplying essential fatty acids (linoleic and alpha-linolenic acids).",
        body_style,
    ))
    story.append(Paragraph(
        "<b>ICMR-NIN Fat Intake Guidelines:</b><br/>"
        "• <b>Visible Fat Allowance:</b> 20g to 30g visible fat per person per day (approximately 4 to 6 teaspoons).<br/>"
        "• <b>Fatty Acid Profile Balance:</b> Diets should maintain an equitable balance between Saturated Fatty Acids (SFA, <8-10% of total energy), Monounsaturated Fatty Acids (MUFA, 10–12%), and Polyunsaturated Fatty Acids (PUFA, 6–8%).<br/>"
        "• <b>Cooking Oil Recommendations:</b> ICMR-NIN recommends rotating or blending cooking oils (such as groundnut/mustard/rice bran oil with sunflower/safflower oil) to optimize the Omega-6 to Omega-3 ratio between 5:1 and 10:1.<br/>"
        "• <b>Omega-3 Fatty Acids:</b> Alpha-linolenic acid (ALA) is concentrated in flaxseeds (Alsi), chia seeds, walnuts, and mustard oil. Marine sources (fatty fish) provide active EPA and DHA.<br/>"
        "• <b>Zero Industrial Trans Fats:</b> Partially hydrogenated vegetable fats (vanaspati, bakery shortenings, reused fried oils) should be completely avoided to prevent cardiovascular disease.",
        body_style,
    ))
    story.append(Spacer(1, 10))

    # Chapter 7: Carbohydrates, Energy Distribution, and Food Synergy
    story.append(Paragraph("Chapter 7: Carbohydrates, Energy Distribution, and Food Synergy", heading_style))
    story.append(Paragraph(
        "Carbohydrates constitute the primary metabolic fuel source for the human brain and muscular contraction. "
        "ICMR-NIN recommends that carbohydrates contribute <b>50% to 55% of total daily energy</b>, and should not exceed 60%.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>Carbohydrate Quality & Glycemic Load:</b><br/>"
        "• <b>Complex Carbohydrates:</b> Found in whole grains, millets, pulses, and fibrous vegetables. These contain long polysaccharide chains that break down slowly, maintaining stable insulin response.<br/>"
        "• <b>Simple Sugars Restriction:</b> Added sugars, confectionery, sugar-sweetened beverages, and ultra-refined flours should be restricted to less than 5% of total caloric intake.<br/>"
        "• <b>Traditional Food Synergy:</b> Combining traditional foods enhances nutrition: (1) Cereal-Pulse combinations (Khichdi, Dosa-Sambar) provide complete amino acids; (2) Adding lemon juice (Vitamin C) to iron-rich green leafy vegetables (Palak, Methi) multiplies iron absorption; (3) Incorporating moderate healthy fat (oil/ghee) with yellow-orange vegetables (carrots, pumpkins) enables provitamin A carotenoid uptake.",
        body_style,
    ))

    doc.build(story)
    print(f"Generated: {pdf_path}")


if __name__ == "__main__":
    build_dietary_guidelines_pdf()
