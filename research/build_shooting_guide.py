"""Build the fMRIght hook-test shooting guide PDF."""
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = sys.argv[1]
F = "/usr/share/fonts/noto/"
pdfmetrics.registerFont(TTFont("Sans", F + "NotoSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", F + "NotoSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Italic", F + "NotoSans-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Semi", F + "NotoSans-SemiBold.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + "NotoSansMono-Regular.ttf"))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Italic",
                              boldItalic="Sans-Bold")

INK = colors.HexColor("#1b2430")
MUTED = colors.HexColor("#5b6675")
ACCENT = colors.HexColor("#0f766e")
ACCENT_BG = colors.HexColor("#e6f4f2")
WARN_BG = colors.HexColor("#fdf3e3")
WARN = colors.HexColor("#9a5b00")
RULE = colors.HexColor("#d5dbe2")
HEAD_BG = colors.HexColor("#eef1f5")
HOOK_C = colors.HexColor("#f2b84b")
BODY_C = colors.HexColor("#8fb8d9")

ss = {
    "title": ParagraphStyle("title", fontName="Sans-Bold", fontSize=24, leading=29, textColor=INK),
    "sub": ParagraphStyle("sub", fontName="Sans", fontSize=11.5, leading=16, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="Sans-Bold", fontSize=16, leading=21, textColor=INK,
                         spaceBefore=14, spaceAfter=6, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Sans-Semi", fontSize=12, leading=16, textColor=ACCENT,
                         spaceBefore=8, spaceAfter=3, keepWithNext=1),
    "p": ParagraphStyle("p", fontName="Sans", fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Sans", fontSize=8.4, leading=11.4, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Sans", fontSize=8.6, leading=11.6, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Sans-Bold", fontSize=8.6, leading=11.6, textColor=INK),
    "bul": ParagraphStyle("bul", fontName="Sans", fontSize=9.6, leading=13.6, textColor=INK,
                          leftIndent=14, bulletIndent=3, spaceAfter=2.5),
    "num": ParagraphStyle("num", fontName="Sans", fontSize=9.6, leading=13.6, textColor=INK,
                          leftIndent=16, bulletIndent=0, spaceAfter=3),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.6, leading=12, textColor=INK,
                           backColor=HEAD_BG, borderPadding=6, leftIndent=6, spaceBefore=4, spaceAfter=8),
    "box": ParagraphStyle("box", fontName="Sans", fontSize=9.6, leading=13.6, textColor=INK),
}

W = letter[0] - 1.5 * inch  # usable width


def P(t, s="p"):
    return Paragraph(t, ss[s])


def bullets(items):
    return [Paragraph(i, ss["bul"], bulletText="•") for i in items]


def numbered(items):
    return [Paragraph(i, ss["num"], bulletText=f"{n}.") for n, i in enumerate(items, 1)]


def table(rows, widths, header=True, bold_first_col=False):
    data = []
    for r, row in enumerate(rows):
        out = []
        for c, cell in enumerate(row):
            style = "cellb" if (header and r == 0) or (bold_first_col and c == 0) else "cell"
            out.append(cell if not isinstance(cell, str) else Paragraph(cell, ss[style]))
        data.append(out)
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1 if header else 0)
    st = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
    t.setStyle(TableStyle(st))
    return t


def callout(text, kind="info"):
    bg, edge = (ACCENT_BG, ACCENT) if kind == "info" else (WARN_BG, WARN)
    t = Table([[Paragraph(text, ss["box"])]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return KeepTogether([t, Spacer(1, 8)])


def timeline():
    """The 20-second variant drawn to scale: 90 opening frames, 510 body frames."""
    lab = ParagraphStyle("lab", parent=ss["cellb"], alignment=1, fontSize=8.4)
    sm = ParagraphStyle("sm", parent=ss["small"], alignment=1, fontSize=7.6, leading=9.6)
    top = [Paragraph("OPENING<br/>0:00–0:03<br/>frames 1–90", lab),
           Paragraph("BODY · 0:03–0:20 · frames 91–600 · identical in all four variants", lab)]
    beats = [Paragraph("spoken / visual<br/>text / cold", sm),
             Paragraph("beat 1<br/>0:03–0:06", sm), Paragraph("beat 2 (proof moment)<br/>0:06–0:12", sm),
             Paragraph("beat 3<br/>0:12–0:17", sm), Paragraph("beat 4<br/>0:17–0:20", sm)]
    fr = [90, 90, 180, 150, 90]
    widths = [W * f / 600 for f in fr]
    t = Table([[top[0], top[1], "", "", ""], beats], colWidths=widths)
    t.setStyle(TableStyle([
        ("SPAN", (1, 0), (4, 0)),
        ("BACKGROUND", (0, 0), (0, 1), HOOK_C),
        ("BACKGROUND", (1, 0), (4, 0), BODY_C),
        ("BACKGROUND", (1, 1), (4, 1), colors.HexColor("#d4e5f2")),
        ("GRID", (0, 0), (-1, -1), 0.8, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return KeepTogether([t, Spacer(1, 4),
                         P("Every variant is exactly 20.00 seconds = 600 frames at 30 frames per second. "
                           "Drawn to scale.", "small"), Spacer(1, 6)])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Sans", 7.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.75 * inch, 0.5 * inch, "fMRIght hook test · Shooting guide · v1 · 2026-10-14")
    canvas.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.line(0.75 * inch, 0.65 * inch, letter[0] - 0.75 * inch, 0.65 * inch)
    canvas.restoreState()


s = []

# ── Cover + one-page summary ───────────────────────────────────────────────
s += [P("fMRIght Hook Test", "title"), P("Shooting guide for Team 2", "sub"), Spacer(1, 4),
      P("Ryan · Lucas (edit lead) · Audrey · Ben (study lead) · Cole · Julie &nbsp;&nbsp;|&nbsp;&nbsp; "
        "v1, 14 Oct 2026", "small"), Spacer(1, 14)]

s.append(callout(
    "<b>The whole guide in one paragraph.</b> We are filming <b>18 product videos</b> (called <b>bases</b>). "
    "Each base exists in <b>4 versions</b> that are identical except for the <b>first 3 seconds</b>. "
    "We run all 72 as Instagram Reels ads with equal budgets and measure how many people watch past "
    "3 seconds. Then we check whether the brain model predicted which opening would win. "
    "The videos must look like real creator ads that brands pay to run, because the people we want to "
    "sell to judge exactly those videos every week."))

s.append(P("What each person does", "h2"))
s += numbered([
    "<b>Everyone:</b> build a swipe file (section 5), list products you own, fill in <b>3 Base Cards</b>.",
    "<b>Lucas:</b> approves every Base Card and picks the best hook for each opening <i>before</i> anyone films.",
    "<b>Each shooter:</b> films and edits their first base. Lucas checks it. Then the other two.",
    "<b>Ben:</b> runs the checker on every base. Anything that fails gets fixed and re-dropped.",
    "<b>Everyone:</b> the guess round, ranking the openings of bases you did <i>not</i> shoot.",
    "<b>Ben:</b> scores all 72 clips with the model, freezes the study, launches the ads.",
])

s.append(P("The five rules that break the study if ignored", "h2"))
s += numbered([
    "Inside a base, the <b>body is identical</b> in all four versions. Same footage, audio, cut, length, to the frame.",
    "Every opening is <b>exactly 3.00 seconds (90 frames)</b>. Every version is <b>exactly 20.00 seconds</b>.",
    "Film at <b>30 fps</b>. Not 24, 29.97 or 60.",
    "<b>No visible brands</b> unless Ben already has the brand's written OK. No copyrighted music.",
    "Nothing that fails ad review: no health claims, before/after shots, supplements, weight loss, alcohol, cannabis.",
])

s.append(PageBreak())

# ── 1. What and who ────────────────────────────────────────────────────────
s.append(P("1. What we are testing, and who it is for", "h1"))
s.append(P("We can run a model that predicts how a human brain responds to a video, from the video file alone. "
           "Nobody has shown whether that prediction says anything useful about short-form video. This study "
           "settles it. If the model adds nothing, we publish that: a clean “no” is a real result."))
s.append(P("The videos have to look like the work our future customers actually judge. If we film generic "
           "clips, any result only speaks for generic clips. If we film what they review every week, a result "
           "becomes something we can put in front of them."))
s.append(table([
    ["Who buys", "Who they are", "What they judge", "Bases"],
    ["<b>Hook-Rate Hunter</b><br/>(Persona C, primary)",
     "Creative strategists and performance marketers at direct-to-consumer (DTC) brands or their agencies. "
     "They launch 10+ creator-style ads a month on Instagram and TikTok.",
     "Paid creator ads. <b>Hook rate is already their main number</b>, the exact thing we measure.", "12"],
    ["<b>Draft Gatekeeper</b><br/>(Persona B, secondary)",
     "Influencer-agency campaign managers and brand creator-program leads. They approve 20+ creator drafts "
     "a month before posting.",
     "Sponsored creator posts, before they go live.", "6"],
    ["<b>Working Creator</b>", "UGC creators and micro-influencers paid to make brand content.",
     "They make what B and C judge, so both sets of bases cover them.", "—"],
], [0.2, 0.37, 0.33, 0.1]))
s.append(Spacer(1, 8))
s.append(callout(
    "<b>Why this design matches real practice.</b> Creative strategists already do “hook stacking”: one body, "
    "3–5 different openings, launched to see which stops the scroll. Their documented pain is “a batch of "
    "8–15 videos arrives and nobody knows which will survive past day 3.” Our four openings on one body are "
    "that exact decision. Only about 5% of their ads end up as winners, so a tool that picks better "
    "openings before spending money is worth real dollars to them."))

# ── 2. Glossary ────────────────────────────────────────────────────────────
s.append(P("2. Words we use (and the ones we avoid)", "h1"))
s.append(P("Use these words exactly. Most mix-ups on a team come from two people meaning different things by "
           "“the video” or “the hook.”"))
s.append(table([
    ["Word", "Meaning", "Don't say"],
    ["<b>Base</b>", "One product video, filmed by one shooter, that exists in four variants. 18 in the study.",
     "video, concept, ad"],
    ["<b>Variant</b>", "One of the four finished files of a base. Identical to the other three except the opening.",
     "version, cut"],
    ["<b>Opening</b>", "The first 3 seconds (90 frames) of a variant. One of: <b>spoken, visual, text, cold</b>.",
     "intro"],
    ["<b>Hook</b>", "What fills an opening to stop the scroll: a spoken line, an on-screen line, or a motion "
                    "moment. The cold opening has <i>no</i> hook.", "(don't use it to mean “opening”)"],
    ["<b>Body</b>", "Everything after 3 seconds. Frame-for-frame identical in all four variants.",
     "main video, content"],
    ["<b>Plate</b>", "A plain 3-second shot of the product, nothing happening. Used for the cold opening and under "
                     "the text opening.", "B-roll, filler"],
    ["<b>Proof moment</b>", "The roughly 2-second shot in the body where you can <i>see</i> the product work.",
     "money shot"],
    ["<b>Base Card</b>", "The one-page plan for a base, filled in before filming (section 6).", "brief, script"],
    ["<b>Body format</b>", "The beat structure the body follows, picked from a fixed menu (section 7).",
     "template, style"],
    ["<b>Swipe file</b>", "Your saved collection of real ads whose structure you can borrow (section 5).",
     "inspo"],
    ["<b>Hook rate</b>", "People who watched 3+ seconds ÷ people the ad was shown to. Our main result.",
     "thumb-stop rate, views"],
    ["<b>Hold rate</b>", "Share of viewers who reach 15 seconds. A secondary result.", "retention"],
    ["<b>Frame</b>", "One still image. At 30 frames per second, 3 seconds = 90 frames.", "—"],
], [0.17, 0.6, 0.23]))



# ── 3. Feel ────────────────────────────────────────────────────────────────
s.append(P("3. What the videos should feel like: “native UGC”", "h1"))
s.append(P("UGC means user-generated content. The target: <b>a real person filming on their phone at home, "
           "a clip a brand would pay to run as an ad.</b> Not a commercial. Polished ads are a different "
           "product that performs differently, and they are not what our buyers review."))
s.append(table([
    ["Do", "Don't"],
    ["Phone camera, window light, real rooms: kitchen counter, bathroom sink, desk, car",
     "Studio lights, gimbal glide shots, perfect staging"],
    ["One person talking like they're telling a friend", "Reading a script word-for-word"],
    ["Hands in frame, the product actually being used", "The product sitting on a pedestal"],
    ["Plain words: “this thing is so good”", "Brand-speak: “revolutionary formula”"],
    ["One honest downside in a review body", "Pure hype (reads fake, and can fail ad review)"],
    ["Captions on everything spoken (section 4)", "Background music by default"],
], [0.5, 0.5]))
s.append(Spacer(1, 6))
s.append(callout("<b>The one-question test:</b> would you believe a friend posted this? If yes, the feel is right."))

# ── 4. Anatomy ─────────────────────────────────────────────────────────────
s.append(P("4. How a base is built", "h1"))
s.append(timeline())
s.append(P("The four openings", "h2"))
s.append(table([
    ["Opening", "What's on screen (0:00–0:03)", "Sound", "Captions / text"],
    ["<b>cold</b>", "The <b>plate</b>: steady close-up of the product, nothing happening.",
     "Room sound only", "None"],
    ["<b>text</b>", "<b>The same plate clip as cold</b>, reused, not reshot.", "Same room sound",
     "The hook line on screen, frame 1 to 90"],
    ["<b>spoken</b>", "The shooter on camera, saying the hook line to the lens.",
     "The voice. <b>Finished by about 2.8 s</b> so it doesn't spill into the body.",
     "Burned-in captions of the line"],
    ["<b>visual</b>", "A motion moment: a fast push-in, the product dropped into frame, or the proof moment "
                      "shown first.", "Natural sound of the action", "None"],
], [0.13, 0.42, 0.25, 0.2]))
s.append(Spacer(1, 6))
s.append(P("Why cold and text share one clip: the only difference between them is then the words on screen, "
           "which makes that comparison clean."))
s.append(P("Captions (decided)", "h2"))
s.append(P("Over 70% of Reels are watched with the sound off. A spoken opening without captions would lose "
           "for that reason alone, which tells us nothing about the brain model, and almost no real UGC ad "
           "ships without captions. So:"))
s += bullets([
    "<b>Every spoken word gets burned-in captions</b>, in the spoken opening and in the body.",
    "Lucas makes <b>two saved style presets</b> and everyone uses them: <b>Caption</b> (for speech) and "
    "<b>Hook text</b> (for the text opening). Same font, size, color and position in every base.",
    "Body captions are created <b>once, on the body</b>, so they are identical in all four variants.",
    "The visual and cold openings have no speech, so no captions.",
])
s.append(P("Where text may go on screen", "h2"))
s.append(P("Instagram covers the top and bottom of a Reel with its own buttons and captions. Keep all text "
           "and the product <b>out of the top 14% and the bottom 35%</b> of the frame (Meta's Reels safe zone). "
           "The middle of the frame is always safe."))



# ── 5. Ideas ───────────────────────────────────────────────────────────────
s.append(P("5. Where the ideas come from", "h1"))
s.append(P("Skilled UGC creators don't invent from scratch. They copy <b>structures</b> that are already "
           "working and fill them with their own product and words. Creative strategists, our main buyer, do "
           "this every week. Most of us haven't made content to grow an audience, so this process does that "
           "job for us."))
s += numbered([
    "<b>Build a swipe file (about 30 minutes).</b> Search your product's category in the "
    "<b>Meta Ad Library</b> (facebook.com/ads/library, free, shows every ad running right now) and in "
    "<b>TikTok Creative Center <font face='Mono'>→</font> Top Ads</b>. Save 5 ads whose first 3 seconds made you stop. For each, "
    "write one line: what happened in the first 3 seconds, and which body format it used.",
    "<b>Copy the structure, never the words or the footage.</b> “Opens on the result, then shows how” is a "
    "structure. Their exact line or clip is not ours to use.",
    "<b>List 6 products you own and actually use.</b> Keep the 3 with the clearest proof moment that also pass "
    "the rules in section 12.",
    "<b>Fill in one Base Card per product</b> (section 6). Write <b>5 hook lines for each opening type</b>. "
    "Volume is how you find a good one; the first idea is rarely the best.",
    "<b>Send your 3 cards to Lucas.</b> He approves them and picks the best hook per opening. Paper is free; "
    "reshoots are not.",
])

# ── 6. Base Card ───────────────────────────────────────────────────────────
s.append(P("6. The Base Card: six blanks per base", "h1"))
s.append(table([
    ["#", "Blank", "What goes in it"],
    ["1", "<b>Product</b>", "Something you own and use. Must pass section 12."],
    ["2", "<b>Persona</b>", "C (paid ad) or B (sponsored post). Each shooter does 2 C and 1 B."],
    ["3", "<b>Problem</b>", "The problem it solves, in one sentence a friend would say. (B bases: the routine "
                            "it lives in instead.)"],
    ["4", "<b>Proof moment</b>", "The 2-second shot where you can see it work. <b>No visible proof moment, "
                                 "no base.</b> This is the most important filter."],
    ["5", "<b>Body format</b>", "One from the menu in section 7."],
    ["6", "<b>Hook lines</b>", "5 per opening type from the menu in section 8. Lucas picks one of each."],
], [0.05, 0.18, 0.77]))
s.append(Spacer(1, 4))
s.append(P("A blank, printable Base Card is the last page of this guide.", "small"))



# ── 7. Body formats ────────────────────────────────────────────────────────
s.append(P("7. Body formats (the 17 seconds after the opening)", "h1"))
s.append(P("Times are in the finished 20-second video. The body always runs 0:03 to 0:20."))
s.append(table([
    ["Format", "For", "Beats"],
    ["<b>Problem <font face='Mono'>→</font> solution</b>", "C",
     "0:03–0:07 already <i>in</i> the problem (don't announce it) · 0:07–0:13 product fixes it (proof moment) · "
     "0:13–0:17 the result · 0:17–0:20 one-line verdict"],
    ["<b>Demo</b>", "C", "0:03–0:06 setup · 0:06–0:12 proof moment · 0:12–0:17 result · 0:17–0:20 verdict"],
    ["<b>Honest review</b>", "C",
     "0:03–0:07 “I've used this for a month” · 0:07–0:13 what's good (proof moment) · 0:13–0:17 one real "
     "downside · 0:17–0:20 verdict"],
    ["<b>Unboxing</b>", "C",
     "0:03–0:07 box open · 0:07–0:10 first look · 0:10–0:16 first use (proof moment) · 0:16–0:20 first reaction"],
    ["<b>3 reasons</b>", "C", "Three ~4-second reasons, each with its own shot · last 3 seconds: verdict"],
    ["<b>Routine integration</b>", "B",
     "A morning, desk, gym, travel or study routine. The product shows up naturally as one step in the middle "
     "(proof moment), then the routine continues."],
], [0.2, 0.06, 0.74]))
s.append(Spacer(1, 8))
s.append(callout("<b>Two rules for every body.</b> (1) <b>Start mid-action.</b> If the body opens with its own "
                 "attention-grabbing line, every variant gets a second hook and the openings stop mattering. "
                 "(2) <b>Never refer back to the opening.</b> No “like I said.” The body has to make sense after "
                 "any of the four openings, including the silent one.", "warn"))

# ── 8. Hook menu ───────────────────────────────────────────────────────────
s.append(P("8. Hook menu, by opening", "h1"))
s.append(P("Each opening type has its own proven hook styles. Pick the strongest one for each type. The four "
           "openings do <b>not</b> have to say the same thing; each should be the best real-world version of "
           "its type. If all four are weak copies of one idea, they all perform the same and there is nothing "
           "for the model to predict."))
s.append(table([
    ["Opening", "Hook styles that work", "Example (milk frother)"],
    ["<b>spoken</b><br/>on camera, captioned",
     "<b>Callout</b>: name who it's for · <b>Question</b> · <b>Confession</b>: “I was today years old…”",
     "“If you drink coffee every morning, you need this.”"],
    ["<b>text</b><br/>over the plate, no voice",
     "<b>POV</b> · <b>“Stop doing X”</b> · <b>Curiosity</b>: “I didn't expect this to work”",
     "“POV: you stopped paying $6 for lattes”"],
    ["<b>visual</b><br/>motion, no voice, no text",
     "<b>Result-first</b>: show the proof moment out of order · <b>Pattern interrupt</b>: the product dropped "
     "into frame, a fast push-in",
     "Foam spilling over the rim of the mug"],
    ["<b>cold</b>", "None. The plate, nothing happening.", "The frother next to a mug, still"],
], [0.2, 0.47, 0.33]))



# ── 9. Category plan ───────────────────────────────────────────────────────
s.append(P("9. What we film: the 18-base plan", "h1"))
s.append(P("<b>12 Persona C bases</b>: 6 high-volume DTC categories that pass ad review, 2 bases each, each "
           "with a different body format, the way real ad accounts test them."))
s.append(table([
    ["Category", "Base A body format", "Base B body format"],
    ["Home & kitchen", "Demo", "Problem <font face='Mono'>→</font> solution"],
    ["Beauty / personal care (no skin claims, no before/after)", "Routine demo", "Honest review"],
    ["Apparel & accessories", "Try-on (demo)", "3 reasons"],
    ["Pet", "Demo with pet", "Unboxing"],
    ["Food & drink (non-alcoholic)", "Taste test (honest review)", "Recipe in 15 seconds (demo)"],
    ["Tech accessories", "Unboxing", "Problem <font face='Mono'>→</font> solution"],
], [0.44, 0.28, 0.28]))
s.append(Spacer(1, 8))
s.append(P("<b>6 Persona B bases</b>, all routine integration, the kind of sponsored draft agencies approve: "
           "morning routine · work-from-home desk day · gym bag · travel packing · study session · "
           "get-ready-with-me."))
s.append(P("Who films what", "h2"))
s += bullets([
    "Each shooter films <b>2 Persona C bases and 1 Persona B base</b>, so Lucas's UGC experience raises quality "
    "across the whole set, not in one corner.",
    "<b>No two bases share a product or category slot.</b> Claim yours in the group chat; first claim wins.",
    "Base numbers stay as assigned: Lucas 01–03, Ryan 04–06, Audrey 07–09, Ben 10–12, Cole 13–15, Julie 16–18.",
])

# ── 10. Worked example ─────────────────────────────────────────────────────
s.append(P("10. Worked example: one base, start to finish", "h1"))
s.append(P("Base 07: a rechargeable milk frother, Persona C, demo format. Use it as the model for your own."))
s.append(P("Step 1 · Plan on paper (15 min)", "h2"))
s.append(table([
    ["Time", "Frames", "What's on screen", "Same in all 4?"],
    ["0:00–0:03", "1–90", "<b>Opening</b> (one of the four in section 4)", "No, the only difference"],
    ["0:03–0:06", "91–180", "Beat 1: hand pours cold milk into a mug", "Yes"],
    ["0:06–0:12", "181–360", "Beat 2: frother in, button press, close-up of foam rising (<b>proof moment</b>)", "Yes"],
    ["0:12–0:17", "361–510", "Beat 3: foam poured over coffee, a sip", "Yes"],
    ["0:17–0:20", "511–600", "Beat 4: product held to camera: “Honestly, my favorite $20 buy.”", "Yes"],
], [0.13, 0.12, 0.53, 0.22]))

s.append(P("Step 2 · Camera setup (5 min, once, then don't touch it)", "h2"))
s.append(P("iPhone menu names shown; Android has the same options under similar names.", "small"))
s += bullets([
    "<b>Settings <font face='Mono'>→</font> Camera <font face='Mono'>→</font> Record Video <font face='Mono'>→</font> 4K at 30 fps.</b> Not 24, not 60. The checker rejects anything but exactly 30.",
    "<b>Turn off “Auto FPS.”</b> It quietly drops the frame rate in dim light.",
    "<b>Turn off “HDR Video.”</b> HDR looks washed out after export and shifts color between clips.",
    "<b>Lock focus and exposure:</b> long-press the subject until “AE/AF Lock” appears.",
    "<b>Vertical, 1× zoom</b> (no digital zoom), clean lens.",
    "<b>Light:</b> one window to the side, every shot in one session. Not the body at noon and the openings at dusk.",
    "<b>Sound:</b> a clip-on mic if you have one, otherwise the phone about arm's length away in a quiet room. "
    "Record <b>10 seconds of silence</b> (room tone) at the end so the editor can fill gaps.",
])

s.append(P("Step 3 · Shot list (about 45 min)", "h2"))
s.append(table([
    ["Shot", "Takes", "Notes"],
    ["Body beats 1–4", "3 each", "Start every take mid-action. Speak naturally, don't read."],
    ["Plate", "1 (6 seconds long)", "Steady, nothing moving. It becomes both the cold and the text opening."],
    ["Spoken opening", "5", "Look into the lens. Finish the line by about 2.8 seconds."],
    ["Visual opening", "5", "The motion moment. No talking."],
    ["Room tone", "1 (10 seconds)", "Silence in the same room, nobody moving."],
], [0.22, 0.18, 0.6]))

s.append(P("Step 4 · Edit (Lucas or the shooter, about 45 min)", "h2"))
s += numbered([
    "<b>Edit the body once</b>: beats 1–4, color, sound level, captions (Caption preset). Export it as one file, "
    "<font face='Mono'>base07_body_master.mov</font>. From here on, <b>nobody edits the body</b>. Reusing one "
    "exported file is what keeps all four bodies identical.",
    "<b>Cut four openings, each exactly 3.00 seconds (90 frames).</b> Check the clip length in the editor: "
    "2.97 or 3.03 seconds fails. Add the Hook text preset to the text opening and captions to the spoken opening.",
    "<b>Build four projects:</b> one opening + <font face='Mono'>base07_body_master.mov</font>.",
    "<b>Sound level:</b> the body is already set. Match each opening to it by ear. <b>Do not</b> press "
    "“normalize” on the finished files; that re-levels the body differently in each version.",
    "<b>Export all four with one saved preset:</b> MP4, H.264, 1080 × 1920, 30 fps constant, AAC audio.",
    "<b>Name the files exactly:</b> <font face='Mono'>base07_cold.mp4 · base07_text.mp4 · base07_spoken.mp4 · "
    "base07_visual.mp4</font>. Any other name is ignored by the checker.",
    "<b>Drop them</b> in the shared <font face='Mono'>stimuli</font> folder and add one row per file to the "
    "shared sheet: base, variant, the hook as written, category, body format, persona, anything unusual.",
])

s.append(P("Step 5 · Check (Ben, 2 min)", "h2"))
s.append(Paragraph("cd research &amp;&amp; make validate-stimuli STIMULI_DIR=/path/to/stimuli", ss["code"]))
s.append(P("<b>PASS</b> means the base is a fair test. <b>FAIL</b> says exactly what's wrong, for example "
           "“visual's body starts 1 frame early” or “loudness −15.4 LUFS, need −14 ±1.” Fix that one variant and "
           "re-drop it. The checker never judges whether a hook is good, only whether the test is fair."))



# ── 11. Examples ───────────────────────────────────────────────────────────
s.append(P("11. Three filled-in Base Cards", "h1"))
s.append(table([
    ["", "Base A", "Base B", "Base C"],
    ["Product", "Milk frother", "Pet-hair roller", "Insulated water bottle"],
    ["Persona", "C", "C", "B"],
    ["Problem", "“Café foam at home is impossible”", "“Dog hair on the couch never comes off”",
     "(routine: a work-from-home desk day)"],
    ["Proof moment", "Foam rising in the mug", "One roll leaves a clean stripe through the hair",
     "Ice still in it at 5 pm"],
    ["Body format", "Demo", "Problem <font face='Mono'>→</font> solution", "Routine integration"],
    ["spoken", "“If you drink coffee every morning, you need this.”", "“Dog owners, I found the thing.”",
     "“This is the only thing on my desk I'd rebuy.”"],
    ["text", "“POV: you stopped paying $6 for lattes”", "“Stop using tape on your couch”",
     "“5 pm and there's still ice in it”"],
    ["visual", "Foam spilling over the rim", "Roller dragged through a hairy cushion, clean stripe",
     "Ice rattling as the bottle is shaken toward the camera"],
    ["cold", "Frother next to a mug, still", "Roller on the couch arm, still", "Bottle on the desk, still"],
], [0.16, 0.28, 0.28, 0.28], bold_first_col=True))

# ── 12. Rules ──────────────────────────────────────────────────────────────
s.append(P("12. Rules that don't bend", "h1"))
s.append(table([
    ["Area", "Rule", "Why"],
    ["Specs", "1080 × 1920 vertical · exactly 30 fps · every variant 20.00 s · openings exactly 90 frames · "
              "sound at −14 LUFS ±1 (the checker measures it)", "The checker rejects anything else"],
    ["Brands", "No visible logos or brand names (tape over or turn away) <b>unless Ben already has the brand's "
               "written OK</b> to run paid ads. Want to feature a brand? Send Ben the contact first.",
     "Our ad account would be advertising their product. A creator's whitelisting or usage-rights deal "
     "doesn't cover that; those rights go from creator to brand, not the other way."],
    ["Ad review", "No health or skin claims, no before/after, no supplements, weight loss, alcohol, cannabis, "
                  "money claims", "A rejected variant kills its whole base"],
    ["Music", "None by default. Royalty-free only, with Lucas's OK, and in the body only (never across the "
              "3-second cut)", "Copyrighted music gets ads muted or rejected"],
    ["People", "Nobody on camera who hasn't agreed to appear in ads", "Consent"],
    ["The body", "Never re-trim, re-color or re-level the body inside one variant",
     "Different bodies = the base measures nothing"],
], [0.12, 0.5, 0.38], bold_first_col=True))
s.append(Spacer(1, 8))
s.append(P("Permission (everyone who films replies with this or equivalent wording)", "h2"))
s.append(callout("“I filmed these clips and I own them. I give Team 2 permission to run them as paid ads for a "
                 "research study and to publish the results in aggregate. I keep copyright. I can withdraw the "
                 "clips any time before publication. I want to be credited by name / I prefer not to be named.”"))

# ── 13. Still open ─────────────────────────────────────────────────────────
s.append(P("13. Still being decided (don't act on these yet)", "h1"))
s += bullets([
    "<b>Brand permission in the pre-registration.</b> The registered plan currently bans third-party brands "
    "outright. Ben will amend it to allow brands with written permission before the study is frozen. Until "
    "then, hide logos.",
    "<b>Delivery format.</b> Possibly shooters hand over 5 files per base (body master + 4 raw openings) and a "
    "script stitches and levels them, so frame alignment and loudness can't go wrong. Until decided, follow "
    "Step 4.",
    "<b>A model check on the first base.</b> Ben may score the first finished base with the brain model before "
    "the rest are filmed, to confirm it reads the openings at all.",
])

s.append(PageBreak())

# ── Appendix: blank card ───────────────────────────────────────────────────
s.append(P("Base Card (print one per base)", "h1"))
s.append(P("Base number: ________ &nbsp;&nbsp; Shooter: ______________________ &nbsp;&nbsp; "
           "Approved by Lucas: [  ] &nbsp; Date: __________"))
s.append(Spacer(1, 6))
blank = Paragraph("&nbsp;", ss["cell"])


def card_row(label, hint):
    return [Paragraph(f"<b>{label}</b><br/><font size=7.6 color='#5b6675'>{hint}</font>", ss["cell"]), blank]


rows = [
    card_row("1 · Product", "Owned, used, passes the rules"),
    card_row("2 · Persona", "Circle one: &nbsp; C (paid ad) &nbsp; / &nbsp; B (sponsored post)"),
    card_row("3 · Problem", "One sentence a friend would say (B: the routine)"),
    card_row("4 · Proof moment", "The 2-second shot where you SEE it work"),
    card_row("5 · Body format", "Problem <font face='Mono'>→</font> solution · Demo · Honest review · Unboxing · 3 reasons · Routine"),
    card_row("6a · spoken hooks", "5 lines. Callout · Question · Confession. Circle Lucas's pick"),
    card_row("6b · text hooks", "5 lines. POV · Stop doing X · Curiosity. Circle Lucas's pick"),
    card_row("6c · visual hook ideas", "Result-first · Pattern interrupt"),
    card_row("Plate (cold)", "What sits still in frame"),
    card_row("Body beats", "Beat 1 / 2 (proof) / 3 / 4, one line each"),
]
heights = [0.55, 0.6, 0.65, 0.6, 0.75, 1.3, 1.3, 0.9, 0.5, 1.05]
ct = Table(rows, colWidths=[0.3 * W, 0.7 * W], rowHeights=[h * inch for h in heights])
ct.setStyle(TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.6, RULE),
    ("BACKGROUND", (0, 0), (0, -1), HEAD_BG),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
]))
s.append(ct)

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                        topMargin=0.7 * inch, bottomMargin=0.85 * inch,
                        title="fMRIght Hook Test — Shooting Guide", author="Ben Rippere",
                        subject="Team 2 shooting guide for the hook-test corpus")
doc.build(s, onFirstPage=footer, onLaterPages=footer)
print("wrote", OUT)
