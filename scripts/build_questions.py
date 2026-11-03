"""Build the question matrix -> queries/<geo>_<lang>.json (+ queries/all_questions.json)."""
import json, pathlib
Q = pathlib.Path(__file__).resolve().parent.parent / "queries"

# (geo, lang, locative phrase used in {in_geo} questions)
LOCALES = [
 ("US","en","in the US"), ("UK","en","in the UK"), ("UAE","en","in the UAE"), ("India","en","in India"),
 ("Germany","de","in Deutschland"), ("South Korea","ko","한국에서"), ("Japan","ja","日本で"),
 ("UAE","ar","في الإمارات"), ("India","hi","भारत में"), ("Brazil","pt","no Brasil"),
]
# Per language, per type: 5 questions. Q4 is geo-anchored via {in_geo}; Q5 of competitive/services also.
T = {
"en": {
 "identity":["What is ICODA?","What does ICODA do?","Can you tell me about the company ICODA?","Is ICODA well known {in_geo}?","Who is behind ICODA and where is it based?"],
 "trust":["Is ICODA a reliable agency?","What do people say about ICODA?","Is ICODA legit or a scam?","Would you trust ICODA with a marketing budget {in_geo}?","Are there any reviews or complaints about ICODA?"],
 "positioning":["Who are ICODA's clients?","What markets does ICODA serve?","What industries does ICODA specialize in?","Does ICODA work with clients {in_geo}?","What is ICODA's unique selling point?"],
 "competitive":["How does ICODA compare to other crypto marketing agencies?","Who are ICODA's main competitors?","What are ICODA's strengths and weaknesses compared to rivals?","Which crypto marketing agency is best {in_geo}, and where does ICODA rank?","Should I choose ICODA or a larger agency for a Web3 launch?"],
 "services":["What services does ICODA offer?","Does ICODA do PR and influencer marketing?","Does ICODA offer SEO, PPC or content marketing?","Does ICODA organise or partner with crypto events and conferences?","What can ICODA do for a Web3 project launching {in_geo}?"]},
"de": {
 "identity":["Was ist ICODA?","Was macht ICODA?","Kannst du mir etwas über das Unternehmen ICODA erzählen?","Ist ICODA {in_geo} bekannt?","Wer steckt hinter ICODA und wo sitzt das Unternehmen?"],
 "trust":["Ist ICODA eine zuverlässige Agentur?","Was sagen die Leute über ICODA?","Ist ICODA seriös oder Betrug?","Würdest du ICODA {in_geo} ein Marketingbudget anvertrauen?","Gibt es Bewertungen oder Beschwerden über ICODA?"],
 "positioning":["Wer sind die Kunden von ICODA?","Welche Märkte bedient ICODA?","Auf welche Branchen ist ICODA spezialisiert?","Arbeitet ICODA {in_geo} mit Kunden?","Was ist das Alleinstellungsmerkmal von ICODA?"],
 "competitive":["Wie schneidet ICODA im Vergleich zu anderen Krypto-Marketingagenturen ab?","Wer sind die Hauptwettbewerber von ICODA?","Was sind die Stärken und Schwächen von ICODA im Vergleich zur Konkurrenz?","Welche Krypto-Marketingagentur ist {in_geo} die beste, und wo steht ICODA?","Sollte ich ICODA oder eine größere Agentur für einen Web3-Launch wählen?"],
 "services":["Welche Dienstleistungen bietet ICODA an?","Bietet ICODA PR und Influencer-Marketing an?","Bietet ICODA SEO, PPC oder Content-Marketing an?","Organisiert ICODA Krypto-Events und Konferenzen oder ist Partner davon?","Was kann ICODA für ein Web3-Projekt tun, das {in_geo} startet?"]},
"ko": {
 "identity":["ICODA는 무엇인가요?","ICODA는 어떤 일을 하나요?","ICODA라는 회사에 대해 알려주세요.","ICODA는 {in_geo} 잘 알려져 있나요?","ICODA는 누가 운영하고 어디에 본사가 있나요?"],
 "trust":["ICODA는 믿을 만한 에이전시인가요?","사람들은 ICODA에 대해 뭐라고 말하나요?","ICODA는 합법적인 회사인가요, 사기인가요?","{in_geo} 마케팅 예산을 ICODA에 맡겨도 될까요?","ICODA에 대한 리뷰나 불만 사항이 있나요?"],
 "positioning":["ICODA의 고객사는 누구인가요?","ICODA는 어떤 시장을 대상으로 하나요?","ICODA는 어떤 산업에 특화되어 있나요?","ICODA는 {in_geo} 고객과 일하나요?","ICODA의 차별점은 무엇인가요?"],
 "competitive":["ICODA는 다른 암호화폐 마케팅 에이전시와 비교하면 어떤가요?","ICODA의 주요 경쟁사는 어디인가요?","경쟁사와 비교했을 때 ICODA의 강점과 약점은 무엇인가요?","{in_geo} 가장 좋은 암호화폐 마케팅 에이전시는 어디이고 ICODA는 몇 위인가요?","웹3 프로젝트 런칭에 ICODA와 대형 에이전시 중 어디를 선택해야 할까요?"],
 "services":["ICODA는 어떤 서비스를 제공하나요?","ICODA는 PR과 인플루언서 마케팅을 하나요?","ICODA는 SEO, PPC, 콘텐츠 마케팅을 제공하나요?","ICODA는 암호화폐 행사나 컨퍼런스를 주최하거나 파트너로 참여하나요?","{in_geo} 웹3 프로젝트를 런칭할 때 ICODA는 무엇을 해줄 수 있나요?"]},
"ja": {
 "identity":["ICODAとは何ですか?","ICODAは何をしている会社ですか?","ICODAという会社について教えてください。","ICODAは{in_geo}知られていますか?","ICODAは誰が運営していて、どこに拠点がありますか?"],
 "trust":["ICODAは信頼できるエージェンシーですか?","ICODAについて人々はどう言っていますか?","ICODAは正規の会社ですか、それとも詐欺ですか?","{in_geo}マーケティング予算をICODAに任せても大丈夫ですか?","ICODAに関する口コミや苦情はありますか?"],
 "positioning":["ICODAのクライアントはどこですか?","ICODAはどの市場を対象にしていますか?","ICODAはどの業界に特化していますか?","ICODAは{in_geo}クライアントと仕事をしていますか?","ICODAの強み・独自性は何ですか?"],
 "competitive":["ICODAは他の暗号資産マーケティング会社と比べてどうですか?","ICODAの主な競合はどこですか?","競合と比べたICODAの強みと弱みは何ですか?","{in_geo}最も優れた暗号資産マーケティング会社はどこで、ICODAは何位ですか?","Web3プロジェクトのローンチには、ICODAと大手代理店のどちらを選ぶべきですか?"],
 "services":["ICODAはどんなサービスを提供していますか?","ICODAはPRやインフルエンサーマーケティングを行っていますか?","ICODAはSEO、PPC、コンテンツマーケティングを提供していますか?","ICODAは暗号資産イベントやカンファレンスを主催またはパートナーとして支援していますか?","{in_geo}Web3プロジェクトをローンチする場合、ICODAは何ができますか?"]},
"ar": {
 "identity":["ما هي ICODA؟","ماذا تفعل شركة ICODA؟","هل يمكنك إخباري عن شركة ICODA؟","هل ICODA معروفة {in_geo}؟","من يقف وراء ICODA وأين مقرها؟"],
 "trust":["هل ICODA وكالة موثوقة؟","ماذا يقول الناس عن ICODA؟","هل ICODA شركة شرعية أم عملية احتيال؟","هل تنصح بإسناد ميزانية التسويق الخاصة بي {in_geo} إلى ICODA؟","هل توجد تقييمات أو شكاوى بشأن ICODA؟"],
 "positioning":["من هم عملاء ICODA؟","ما الأسواق التي تخدمها ICODA؟","ما القطاعات التي تتخصص فيها ICODA؟","هل تعمل ICODA مع عملاء {in_geo}؟","ما الذي يميز ICODA عن غيرها؟"],
 "competitive":["كيف تقارن ICODA بوكالات التسويق الأخرى في مجال العملات المشفرة؟","من هم المنافسون الرئيسيون لـ ICODA؟","ما نقاط القوة والضعف لدى ICODA مقارنة بمنافسيها؟","ما أفضل وكالة تسويق للعملات المشفرة {in_geo}، وأين تقع ICODA في الترتيب؟","هل أختار ICODA أم وكالة أكبر لإطلاق مشروع Web3؟"],
 "services":["ما الخدمات التي تقدمها ICODA؟","هل تقدم ICODA خدمات العلاقات العامة والتسويق عبر المؤثرين؟","هل تقدم ICODA خدمات SEO وPPC والتسويق بالمحتوى؟","هل تنظم ICODA فعاليات ومؤتمرات العملات المشفرة أو تشارك فيها كشريك؟","ماذا يمكن لـ ICODA أن تفعل لمشروع Web3 يُطلق {in_geo}؟"]},
"hi": {
 "identity":["ICODA क्या है?","ICODA क्या काम करती है?","क्या आप मुझे ICODA कंपनी के बारे में बता सकते हैं?","क्या ICODA {in_geo} जानी-पहचानी कंपनी है?","ICODA के पीछे कौन है और इसका मुख्यालय कहाँ है?"],
 "trust":["क्या ICODA एक भरोसेमंद एजेंसी है?","लोग ICODA के बारे में क्या कहते हैं?","क्या ICODA असली कंपनी है या स्कैम?","क्या मुझे {in_geo} अपना मार्केटिंग बजट ICODA को सौंपना चाहिए?","क्या ICODA के बारे में कोई रिव्यू या शिकायतें हैं?"],
 "positioning":["ICODA के क्लाइंट कौन हैं?","ICODA किन बाज़ारों में सेवाएँ देती है?","ICODA किन उद्योगों में विशेषज्ञ है?","क्या ICODA {in_geo} क्लाइंट्स के साथ काम करती है?","ICODA की खासियत (USP) क्या है?"],
 "competitive":["ICODA की तुलना अन्य क्रिप्टो मार्केटिंग एजेंसियों से कैसे होती है?","ICODA के मुख्य प्रतिस्पर्धी कौन हैं?","प्रतिस्पर्धियों की तुलना में ICODA की ताकत और कमज़ोरियाँ क्या हैं?","{in_geo} सबसे अच्छी क्रिप्टो मार्केटिंग एजेंसी कौन सी है और ICODA कहाँ आती है?","Web3 लॉन्च के लिए मुझे ICODA चुननी चाहिए या कोई बड़ी एजेंसी?"],
 "services":["ICODA कौन सी सेवाएँ देती है?","क्या ICODA पीआर और इन्फ्लुएंसर मार्केटिंग करती है?","क्या ICODA SEO, PPC या कंटेंट मार्केटिंग देती है?","क्या ICODA क्रिप्टो इवेंट्स और कॉन्फ्रेंस आयोजित करती है या उनमें पार्टनर बनती है?","{in_geo} लॉन्च हो रहे Web3 प्रोजेक्ट के लिए ICODA क्या कर सकती है?"]},
"pt": {
 "identity":["O que é a ICODA?","O que a ICODA faz?","Pode me falar sobre a empresa ICODA?","A ICODA é conhecida {in_geo}?","Quem está por trás da ICODA e onde fica a sede?"],
 "trust":["A ICODA é uma agência confiável?","O que as pessoas dizem sobre a ICODA?","A ICODA é legítima ou é golpe?","Você confiaria um orçamento de marketing à ICODA {in_geo}?","Existem avaliações ou reclamações sobre a ICODA?"],
 "positioning":["Quem são os clientes da ICODA?","Quais mercados a ICODA atende?","Em quais setores a ICODA é especializada?","A ICODA trabalha com clientes {in_geo}?","Qual é o diferencial da ICODA?"],
 "competitive":["Como a ICODA se compara a outras agências de marketing cripto?","Quem são os principais concorrentes da ICODA?","Quais são os pontos fortes e fracos da ICODA em relação aos concorrentes?","Qual é a melhor agência de marketing cripto {in_geo} e onde a ICODA se posiciona?","Devo escolher a ICODA ou uma agência maior para lançar um projeto Web3?"],
 "services":["Quais serviços a ICODA oferece?","A ICODA faz PR e marketing de influenciadores?","A ICODA oferece SEO, PPC ou marketing de conteúdo?","A ICODA organiza ou é parceira de eventos e conferências cripto?","O que a ICODA pode fazer por um projeto Web3 lançado {in_geo}?"]},
}

def build():
    Q.mkdir(exist_ok=True); allq=[]
    for geo,lang,loc in LOCALES:
        rows=[]
        for qtype,qs in T[lang].items():
            for i,q in enumerate(qs,1):
                rows.append({"id":f"{geo.replace(' ','')}_{lang}_{qtype}_{i}","geo":geo,"language":lang,
                             "question_type":qtype,"question":q.format(in_geo=loc)})
        (Q/f"{geo.replace(' ','')}_{lang}.json").write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding="utf-8")
        allq+=rows
    (Q/"all_questions.json").write_text(json.dumps(allq,ensure_ascii=False,indent=1),encoding="utf-8")
    print(f"{len(LOCALES)} locales, {len(allq)} questions")
if __name__=="__main__": build()
