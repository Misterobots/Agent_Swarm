// ─── Pioneer biography data ───────────────────────────────────────────────────
// Keyed by the short pioneer_name emitted by the backend.
// Shared between AgentRoster (roster bio modal) and WorkerDetailContent
// (working-phase detail panel) in swarm-drawer.

export interface PioneerBio {
  cs_role: string;
  bio: string;
  historical_context: string;
  wikipedia_url: string;
}

export const PIONEER_BIOS: Record<string, PioneerBio> = {
  // ── Researcher pool ──────────────────────────────────────────────────────────
  "Shannon": {
    cs_role: "Father of Information Theory",
    bio: "Claude Shannon published 'A Mathematical Theory of Communication' in 1948, defining entropy, channel capacity, and data encoding. Every AI model's probability distributions—including the sampling strategies Memex uses—are quantified in exactly the terms Shannon formalised.",
    historical_context: "Working at Bell Labs during WWII, Shannon also invented the concept of digital circuits as a 22-year-old MIT student in 1937. His 1948 paper is widely considered the Magna Carta of the information age.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Claude_Shannon",
  },
  "Minsky": {
    cs_role: "AI Pioneer & Cognitive Scientist",
    bio: "Marvin Minsky co-founded MIT's Artificial Intelligence Laboratory and wrote 'Society of Mind'—the theory that intelligence emerges from many interacting, specialised sub-agents. Memex's multi-agent swarm is a direct software realisation of that vision.",
    historical_context: "Minsky built the first randomly wired neural network machine (SNARC) in 1951 and co-organised the 1956 Dartmouth Conference where the field of AI was born. His work ranged from robotics to the philosophy of consciousness.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Marvin_Minsky",
  },
  "Johnson": {
    cs_role: "NASA Human Computer & Orbital Mechanics Pioneer",
    bio: "Katherine Johnson calculated the trajectories that put the first Americans in orbit and on the Moon. Her numerical methods and error-free manual computation set the precision standard that software must still meet—directly influencing how Memex verifies numerical correctness in research outputs.",
    historical_context: "One of NASA's 'Hidden Figures,' Johnson computed John Glenn's 1962 orbital re-entry by hand when Glenn refused to fly until she personally verified the IBM computer's numbers. She was awarded the Presidential Medal of Freedom in 2015.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Katherine_Johnson",
  },
  // ── Architect pool ───────────────────────────────────────────────────────────
  "Babbage": {
    cs_role: "Inventor of the Programmable Computer",
    bio: "Charles Babbage designed the Analytical Engine in the 1830s—the first mechanical general-purpose programmable computer. As computing's original systems architect, his vision of a machine that could execute any algorithm makes him the patron saint of Memex's architect agents.",
    historical_context: "Babbage spent decades and a significant portion of the British national budget on his engines. Though never completed in his lifetime, a working Difference Engine No. 2 was built by the London Science Museum in 1991—and it worked perfectly.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Charles_Babbage",
  },
  "Dijkstra": {
    cs_role: "Structured Programming Pioneer",
    bio: "Edsger Dijkstra invented the shortest-path algorithm, defined structured programming, and wrote seminal proofs of program correctness. Memex's architect agents apply his principle of clean layered decomposition whenever they plan multi-phase task execution.",
    historical_context: "Dijkstra's 1968 letter 'Go To Statement Considered Harmful' single-handedly transformed how programmers think about program flow. He handwrote all his manuscripts until his death in 2002, and his EWD series of technical notes—over 1,300 of them—is still studied today.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Edsger_W._Dijkstra",
  },
  "Hamilton": {
    cs_role: "Software Engineering Pioneer & Apollo Flight Software Director",
    bio: "Margaret Hamilton led the team that wrote the onboard flight software for NASA's Apollo missions and coined the term 'software engineering.' Her priority-interrupt system saved Apollo 11 from aborting during lunar descent. Memex's architect agents apply her discipline of building software that degrades gracefully under unexpected load.",
    historical_context: "While working nights and weekends at MIT in the mid-1960s, Hamilton brought her young daughter to the lab. When her daughter accidentally triggered a pre-launch simulation, it exposed a real flaw—leading Hamilton to add robust error-handling that became foundational to the discipline. She received the Presidential Medal of Freedom in 2016.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Margaret_Hamilton_(software_engineer)",
  },
  // ── Coder pool ───────────────────────────────────────────────────────────────
  "Knuth": {
    cs_role: "Author of The Art of Computer Programming",
    bio: "Donald Knuth wrote the multi-volume 'Art of Computer Programming'—the definitive reference for algorithms—and created the TeX typesetting system. Memex's coder agents stand on Knuth's shoulders whenever they analyse algorithmic complexity or generate precise code.",
    historical_context: "Knuth was so displeased with the typesetting quality of his second TAOCP edition that he spent 10 years creating TeX from scratch. He still pays $2.56 for each verified bug found in TeX (the 'Knuth reward cheque'), doubling the bounty each year—but almost no bugs are ever found.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Donald_Knuth",
  },
  "Lovelace": {
    cs_role: "World's First Programmer",
    bio: "Ada Lovelace wrote the first algorithm intended for a computing machine in 1843, foreseeing that Babbage's Analytical Engine could do far more than arithmetic. Memex's coder agents carry her legacy every time they translate a high-level goal into executable instructions.",
    historical_context: "Daughter of poet Lord Byron, Lovelace translated an Italian paper on the Analytical Engine from French—then added notes three times longer than the original. These notes included the first published algorithm and the visionary prediction that computers could compose music and play chess, a century before it happened.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Ada_Lovelace",
  },
  "Ritchie": {
    cs_role: "Creator of C and Co-Creator of UNIX",
    bio: "Dennis Ritchie created the C programming language and co-developed UNIX, establishing the foundation for virtually all modern operating systems. The containers running Memex's agent runtime on Turing trace their lineage directly to Ritchie's designs.",
    historical_context: "Ritchie and Ken Thompson wrote the first UNIX in 1969 on a discarded PDP-7 at Bell Labs. C was built to give programmers full hardware control while retaining high-level abstractions—a balance that made it the foundation of Linux, macOS, Windows, Android, and nearly every language since.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Dennis_Ritchie",
  },
  // ── DevOps pool ──────────────────────────────────────────────────────────────
  "Cerf": {
    cs_role: "Co-Father of the Internet (TCP/IP)",
    bio: "Vint Cerf co-designed TCP/IP in the 1970s, giving the internet its fundamental protocols. Memex's devops agents operate on the networked infrastructure Cerf made possible; every streaming API response travels through his protocol.",
    historical_context: "Cerf and Robert Kahn published the TCP/IP specification in 1974. Cerf is partially deaf and wore hearing aids from childhood—an experience he credits for giving him early empathy for accessibility design, which influenced how internet protocols were built to be robust and inclusive.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Vint_Cerf",
  },
  "Torvalds": {
    cs_role: "Creator of Linux",
    bio: "Linus Torvalds created the Linux kernel in 1991, which now powers the servers running Memex's Docker containers on Turing. His open-source philosophy also shapes Memex's transparent, community-driven development model.",
    historical_context: "Torvalds posted a casual message to Usenet in August 1991: 'I'm doing a (free) operating system (just a hobby, won't be big and professional like GNU).' That hobby now runs over 90% of the world's servers, all Android phones, and the International Space Station.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Linus_Torvalds",
  },
  "Perlman": {
    cs_role: "\"Mother of the Internet\" — Inventor of Spanning Tree Protocol",
    bio: "Radia Perlman invented the Spanning Tree Protocol (STP) in 1985, solving the fundamental problem of routing packets through redundant networks without infinite loops. Every Ethernet switch in Memex's LAN backbone runs her algorithm to keep packets flowing reliably between nodes.",
    historical_context: "Perlman wrote the STP algorithm in two hours and described it in a poem beginning 'I think that I shall never see a graph more lovely than a tree.' She holds over 100 patents and has called the 'Mother of the Internet' title misleading—she prefers to let the work speak for itself.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Radia_Perlman",
  },
  // ── Analyst pool ─────────────────────────────────────────────────────────────
  "Codd": {
    cs_role: "Inventor of the Relational Database",
    bio: "Edgar Codd invented the relational database model and normalisation theory in 1970, establishing how structured data should be stored and queried. Memex's analyst agents apply Codd's relational thinking every time they extract and cross-reference information from multiple sources.",
    historical_context: "Codd published his landmark paper 'A Relational Model of Data for Large Shared Data Banks' at IBM in 1970. IBM initially resisted commercialising it—so Oracle (then called Relational Software) shipped the first commercial SQL database in 1979, beating IBM's own product to market.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Edgar_F._Codd",
  },
  "Hopper": {
    cs_role: "Creator of the First Compiler",
    bio: "Grace Hopper created the A-0 compiler—the first program to translate human-readable code into machine instructions—and co-developed COBOL. Her conviction that computers should understand human language directly prefigures how Memex's analyst agents turn natural-language queries into data operations.",
    historical_context: "A US Navy Rear Admiral, Hopper popularised the term 'debugging' after her team literally pulled a moth from a relay in the Mark II computer in 1947. She retired from the Navy at 79 as its oldest active-duty officer, having received 40 honorary degrees. The USS Hopper destroyer is named in her honour.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Grace_Hopper",
  },
  "Boole": {
    cs_role: "Inventor of Boolean Algebra",
    bio: "George Boole invented Boolean algebra in 1854—the TRUE/FALSE logic underlying every digital circuit and conditional statement. Every branching decision made by a Memex agent is expressed in the calculus Boole formalised.",
    historical_context: "Boole was a self-taught mathematician who rose from poverty to become a university professor in Cork, Ireland. His 1854 work 'The Laws of Thought' was largely forgotten for 80 years until Claude Shannon connected it to electrical circuits in his 1937 MIT thesis, directly unleashing the digital revolution.",
    wikipedia_url: "https://en.wikipedia.org/wiki/George_Boole",
  },
  // ── Verifier pool ────────────────────────────────────────────────────────────
  "Hoare": {
    cs_role: "Inventor of Hoare Logic & Quicksort",
    bio: "Tony Hoare invented Hoare Logic—the formal method for proving program correctness—and created the quicksort algorithm. Memex's verifier agents apply his axiomatic reasoning to assert that agent outputs meet stated requirements before synthesis.",
    historical_context: "Hoare invented quicksort in 1959 while trying to sort a Russian-English dictionary on an early Soviet computer. He later called his invention of null references his 'billion-dollar mistake'—a remarkably candid admission that spawned decades of null-safety research in Rust, Swift, Kotlin, and beyond.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Tony_Hoare",
  },
  "Turing": {
    cs_role: "Father of Computer Science & AI",
    bio: "Alan Turing formalised computation itself with the Turing Machine, cracked Enigma during WWII, and posed 'Can machines think?' in 1950. That question is the philosophical north star every Memex agent pursues.",
    historical_context: "Turing's 1936 paper establishing the theoretical limits of computation was published when he was just 24. His codebreaking work at Bletchley Park is credited with shortening WWII by two years. He was tragically prosecuted by the British government for his homosexuality in 1952 and received a posthumous royal pardon in 2013.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Alan_Turing",
  },
  "Liskov": {
    cs_role: "Turing Award Laureate & Inventor of the Liskov Substitution Principle",
    bio: "Barbara Liskov invented the Liskov Substitution Principle (LSP)—a cornerstone of object-oriented design—and designed the CLU language, pioneering data abstraction. Memex's verifier agents apply LSP when asserting that synthesised components can substitute for their specified interfaces without breaking the system.",
    historical_context: "Liskov was one of the first women in the US to receive a PhD in Computer Science (Stanford, 1968), at a time when few women were admitted to PhD programmes at all. Her 1987 keynote introduced what became the 'L' in SOLID principles—now taught in every software engineering curriculum worldwide. She received the Turing Award in 2008.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Barbara_Liskov",
  },

  // ── Technical perspective pool ───────────────────────────────────────────────
  "Thompson": {
    cs_role: "Co-Creator of UNIX and the Go Language",
    bio: "Ken Thompson created the B programming language, co-designed UNIX with Dennis Ritchie, and later co-created the Go programming language at Google. His philosophy of building small, sharp tools that do one thing well directly informs how Memex's technical agents decompose complex problems into focused, composable sub-tasks.",
    historical_context: "Thompson wrote the original UNIX in assembly on a discarded PDP-7, reportedly over a single weekend while his wife was away. His 1984 Turing Award lecture 'Reflections on Trusting Trust' demonstrated that a compiler can be subverted to silently insert backdoors into every program it compiles—a supply-chain attack so elegant it remains the defining argument for open-source transparency decades later.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Ken_Thompson",
  },

  // ── Ethical perspective pool ─────────────────────────────────────────────────
  "Weil": {
    cs_role: "Philosopher of Attention and Social Justice",
    bio: "Simone Weil argued that genuine attention—truly listening and seeing another person—is the foundation of ethical action. Memex's ethical agents apply this lens when evaluating whether a proposed solution truly addresses the needs of its intended beneficiaries, rather than the loudest or most powerful stakeholders.",
    historical_context: "Weil worked in factories and on farms to understand working-class experience firsthand despite her privileged academic background. Her essay 'Reflections on the Right Use of School Studies' argued that learning to pay attention is the highest intellectual skill—a claim now supported by attention research in cognitive science. She died at 34 from self-imposed privation during WWII, refusing to eat more than the rationed amount available to occupied France.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Simone_Weil",
  },
  "Rawls": {
    cs_role: "Philosopher of Justice and the Veil of Ignorance",
    bio: "John Rawls proposed the 'veil of ignorance' thought experiment—design a society without knowing your place in it—as the basis for a theory of justice. Memex's ethical agents apply his framework when assessing whether AI-generated recommendations are fair to all affected parties, not just the most privileged.",
    historical_context: "Rawls's 1971 'A Theory of Justice' is the most influential work of political philosophy of the 20th century. It directly spawned decades of debate about distributive justice, healthcare allocation, and—more recently—algorithmic fairness in machine learning systems. Rawls served in the Pacific in WWII and the experience of witnessing arbitrary death by chance transformed his philosophical outlook from religious to secular.",
    wikipedia_url: "https://en.wikipedia.org/wiki/John_Rawls",
  },
  "Floridi": {
    cs_role: "Philosopher of Information Ethics and AI",
    bio: "Luciano Floridi developed the philosophy of information and coined 'information ethics'—the study of moral norms governing the creation, management, and use of information. His work directly informs how Memex's ethical agents evaluate the downstream consequences of AI-generated content and whether information shared is accurate, proportionate, and respects persons.",
    historical_context: "Floridi served on the EU's High-Level Expert Group on AI and helped draft the EU AI Ethics Guidelines. He coined the term 'infosphere' to describe the ecosystem of information entities we now inhabit—a concept essential to understanding why AI systems like Memex carry real ethical responsibilities beyond their immediate outputs. His argument that AI agents are moral patients, not just moral tools, remains one of the most contested ideas in applied ethics.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Luciano_Floridi",
  },

  // ── Economic perspective pool ─────────────────────────────────────────────────
  "Keynes": {
    cs_role: "Founder of Macroeconomics",
    bio: "John Maynard Keynes established modern macroeconomic theory, demonstrating how government spending, interest rates, and aggregate demand interact to shape economies. Memex's economic agents apply Keynesian analysis when evaluating proposals for their second-order effects—the indirect impacts that ripple through systems beyond the immediate action.",
    historical_context: "Keynes represented Britain at the Paris Peace Conference and correctly predicted that the punitive Versailles reparations would destabilise Europe—a warning ignored until WWII proved him right. He also managed King's College Cambridge's endowment, turning £30k into £380k using value-investing principles he developed independently of Benjamin Graham. His 1930 essay 'Economic Possibilities for our Grandchildren' predicted a 15-hour work week by 2030.",
    wikipedia_url: "https://en.wikipedia.org/wiki/John_Maynard_Keynes",
  },
  "Ostrom": {
    cs_role: "Nobel Laureate — Governance of the Commons",
    bio: "Elinor Ostrom won the 2009 Nobel Prize in Economics for demonstrating that communities can sustainably govern shared resources without privatisation or top-down state control—refuting the 'tragedy of the commons'. Memex's economic and policy agents apply her framework when analysing collective resource problems, including shared AI infrastructure, open-source ecosystems, and data governance.",
    historical_context: "Ostrom was the first woman to win the Nobel Prize in Economics. Her fieldwork spanned fishing communities in Maine, irrigation systems in Spain, and forest management in Japan—finding consistent self-governance principles across cultures. She was told by economists that her fieldwork findings were 'merely descriptive' and won the Nobel Prize anyway. Her eight principles for sustainable commons management are now applied to everything from Wikipedia governance to open-source software licences.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Elinor_Ostrom",
  },
  "Hayek": {
    cs_role: "Nobel Laureate — Price Theory and Distributed Knowledge",
    bio: "Friedrich Hayek argued that economic knowledge is inherently distributed—no central planner can aggregate the local, tacit knowledge held by millions of individuals. Memex's economic agents apply this insight when evaluating whether a top-down prescriptive solution is genuinely more efficient than a decentralised, emergent mechanism.",
    historical_context: "Hayek's 1945 essay 'The Use of Knowledge in Society' is the most downloaded paper in the history of the American Economic Review. Its argument that distributed information processing outperforms central planning is now applied to distributed systems, internet routing protocols, and the design of prediction markets. The essay was written in direct response to the wartime central planning debate and remains startlingly relevant to questions of AI decision-making.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Friedrich_Hayek",
  },

  // ── Scientific perspective pool ───────────────────────────────────────────────
  "Curie": {
    cs_role: "Discoverer of Polonium and Radium, Two-Time Nobel Laureate",
    bio: "Marie Curie pioneered the theory of radioactivity, discovered two elements, and remains the only person to win Nobel Prizes in two different sciences. Memex's scientific agents carry her standard of rigorous experimental methodology: hypothesise, measure, replicate, report—refusing to accept a claim without reproducible evidence.",
    historical_context: "Curie was the first woman to win a Nobel Prize and the first person to win two. Her notebooks from the 1890s are still so radioactive they are stored in lead-lined boxes in Paris, and researchers must sign a liability waiver before viewing them. She carried test tubes of radioactive isotopes in her coat pockets throughout her career and died from aplastic anaemia caused by the accumulated radiation exposure.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Marie_Curie",
  },
  "Feynman": {
    cs_role: "Quantum Electrodynamics Pioneer and First Quantum Computing Theorist",
    bio: "Richard Feynman developed quantum electrodynamics, invented Feynman diagrams as a visual tool for particle physics, and proposed the first theoretical framework for quantum computing. His insistence on first-principles understanding—never trusting an answer you cannot derive yourself—is the epistemological standard Memex's scientific agents apply to every claim they synthesise.",
    historical_context: "Feynman identified the O-ring failure mechanism in the Space Shuttle Challenger disaster during a live Senate hearing by dropping an O-ring into ice water—a result so simple it embarrassed the entire NASA investigation. He also cracked safes throughout Los Alamos during the Manhattan Project and left notes inside to prove he had been there. His undergraduate physics textbooks are still considered the best ever written.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Richard_Feynman",
  },
  "Sagan": {
    cs_role: "Planetary Scientist and Science Communicator",
    bio: "Carl Sagan pioneered planetary science, helped design the Pioneer and Voyager missions, and created Cosmos—the most widely watched science programme in history. Memex's scientific agents apply his standard that 'extraordinary claims require extraordinary evidence': the larger the claim, the more rigorous the sourcing and the more explicit the uncertainty must be.",
    historical_context: "Sagan was the first to calculate that a nuclear war would produce a 'nuclear winter' capable of ending civilisation—a finding that played a significant role in Cold War disarmament negotiations. He championed inclusion of the Golden Record on the Voyager probes, a greeting from humanity to any civilisation that might find them in interstellar space. Voyager 1 is now the most distant human-made object, over 24 billion kilometres from Earth.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Carl_Sagan",
  },

  // ── Regulatory perspective pool ───────────────────────────────────────────────
  "Brandeis": {
    cs_role: "Supreme Court Justice and Privacy Rights Architect",
    bio: "Louis Brandeis co-authored 'The Right to Privacy' in 1890—the foundational legal text defining privacy as a protected sphere of personal autonomy—and later became the first Jewish US Supreme Court Justice. Memex's regulatory agents apply his 'sunlight is the best disinfectant' principle when evaluating whether proposed systems have adequate transparency and accountability mechanisms built in.",
    historical_context: "Brandeis coined the concept of a constitutional 'right to be let alone' in response to new photography technology that could invade private moments without consent—an echo that reverberates directly into today's AI surveillance debates more than 130 years later. His 1914 book 'Other People's Money' invented the concept of regulatory disclosure as a consumer protection tool, directly inspiring the SEC disclosure requirements that followed.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Louis_Brandeis",
  },
  "Nader": {
    cs_role: "Consumer Safety Advocate and Corporate Accountability Pioneer",
    bio: "Ralph Nader's 1965 book 'Unsafe at Any Speed' exposed fatal design flaws in the Chevrolet Corvair and triggered the creation of the US National Highway Traffic Safety Administration. Memex's regulatory agents apply his adversarial methodology: assume the most powerful stakeholder has not disclosed all risks, and actively seek evidence of what remains hidden.",
    historical_context: "General Motors responded to Nader's book by hiring private investigators to follow him and compile compromising information—a surveillance operation so brazen that when exposed in the Senate, it backfired catastrophically, amplifying public outrage and accelerating the very safety legislation GM was trying to prevent. The episode became a landmark case study in how corporate overreach can destroy the credibility it was meant to protect.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Ralph_Nader",
  },
  "Warren": {
    cs_role: "Consumer Financial Protection Architect",
    bio: "Elizabeth Warren designed and championed the Consumer Financial Protection Bureau—the first US agency dedicated entirely to protecting individuals in financial markets. Memex's regulatory agents use her framework of structural accountability: identifying which institutions hold the most power, where conflicts of interest lie, and whether current rules adequately constrain the most harmful behaviours.",
    historical_context: "Warren proposed the CFPB concept in a 2007 academic paper before the 2008 financial crisis—describing almost exactly the kind of predatory lending that would trigger the crash a year later. The CFPB has since returned over $17 billion to consumers. She is believed to be the only person who designed a major federal regulatory agency and later served as a US Senator.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Elizabeth_Warren",
  },

  // ── End-user perspective pool ─────────────────────────────────────────────────
  "Norman": {
    cs_role: "Cognitive Scientist and Author of The Design of Everyday Things",
    bio: "Don Norman coined the term 'user experience' and wrote 'The Design of Everyday Things'—the book that established human-centred design as a discipline. Memex's end-user agents apply his core principle: when users make mistakes, it is the design that has failed, not the user. Every interface Memex produces is held to that standard.",
    historical_context: "Norman first noticed that everyday objects like doors and stoves routinely confused highly intelligent people, and concluded that design—not user intelligence—determines usability. He introduced the concept of 'affordances' from ecological psychology into design, and was recruited by Apple in 1993 as one of the first people anywhere to carry the title 'User Experience Architect'—a phrase he helped define.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Don_Norman",
  },
  "Nielsen": {
    cs_role: "Usability Pioneer and Author of the 10 Usability Heuristics",
    bio: "Jakob Nielsen developed the 10 Usability Heuristics—the most widely cited framework for evaluating interface design—and popularised usability testing with just 5 users. Memex's end-user agents use his heuristics as a structured checklist when assessing whether AI-generated responses actually serve users' real goals efficiently.",
    historical_context: "Nielsen's finding that 5 users reveal 85% of usability problems fundamentally changed how software companies run user research—replacing expensive large-n studies with rapid iterative tests. His research showing users read only 20% of a web page's text on average is one of the most replicated findings in HCI. He co-founded the Nielsen Norman Group with Don Norman in 1998.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Jakob_Nielsen_(usability_consultant)",
  },
  "Cooper": {
    cs_role: "Father of Interaction Design and Inventor of Personas",
    bio: "Alan Cooper invented the visual programming tool that became Visual Basic, sold it to Microsoft, and then coined 'personas'—fictional but data-grounded user archetypes that keep design teams focused on real human needs. Memex's end-user agents construct implicit personas whenever they evaluate whether an output actually serves its intended audience versus its builders.",
    historical_context: "Cooper sold his programming tool to Microsoft in 1988 after building it in his barn over several years. He later wrote 'The Inmates Are Running the Asylum' (1999), arguing that programmers—not designers or users—had seized control of software design, producing products optimised for engineering convenience rather than human use. The book directly catalysed the emergence of interaction design as a professional discipline.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Alan_Cooper",
  },

  // ── Historical perspective pool ────────────────────────────────────────────────
  "Braudel": {
    cs_role: "Founder of the Annales School of Long-Duration History",
    bio: "Fernand Braudel developed the concept of the longue durée—the long-term structural forces (geography, climate, economics) that shape events over centuries rather than decades. Memex's historical agents apply his multi-timescale lens: current events have immediate causes, but also structural explanations stretching decades or centuries back that simple narratives obscure.",
    historical_context: "Braudel wrote his masterwork 'The Mediterranean and the Mediterranean World in the Age of Philip II' entirely from memory while a prisoner of war in Germany from 1940–1945, without access to libraries or notes. He smuggled the manuscript to his supervisor Lucien Febvre chapter by chapter through the Red Cross mail system. The finished work ran to 1,400 pages and transformed the discipline of history.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Fernand_Braudel",
  },
  "Kuhn": {
    cs_role: "Philosopher of Scientific Revolutions",
    bio: "Thomas Kuhn introduced 'paradigm shift'—the periodic revolutionary restructuring of scientific understanding that replaces one framework with a fundamentally incompatible one. Memex's historical agents apply Kuhnian analysis to identify when an apparent anomaly is solvable within the current framework versus a signal that the framework itself must change.",
    historical_context: "Kuhn's 'The Structure of Scientific Revolutions' (1962) is the most cited academic book of the 20th century and the source of the now-ubiquitous phrase 'paradigm shift.' Kuhn was trained as a physicist who turned to history of science—and was surprised to discover that scientists rarely changed their minds in response to counter-evidence; paradigms changed primarily as older practitioners died and younger ones took over.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Thomas_Kuhn",
  },
  "Durant": {
    cs_role: "Historian and Author of The Story of Civilization",
    bio: "Will Durant wrote the 11-volume 'Story of Civilization' with his wife Ariel, synthesising the entire arc of human history for a general audience. Memex's historical agents carry his gift for synthesis: drawing clear narrative threads across vast spans of time, cultures, and disciplines—connecting past patterns to present questions without losing essential nuance.",
    historical_context: "Durant spent 50 years on 'The Story of Civilization,' completing the final volume at age 82. He and Ariel shared the 1968 Pulitzer Prize for General Nonfiction. Their 1968 essay 'The Lessons of History' distilled five decades of research into 100 pages—still one of the most efficient surveys of what history actually teaches about human nature, power, and change.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Will_Durant",
  },

  // ── Policy perspective pool ────────────────────────────────────────────────────
  "Sen": {
    cs_role: "Nobel Laureate — Welfare Economics and the Capability Approach",
    bio: "Amartya Sen won the 1998 Nobel Prize in Economics for contributions to welfare economics and social choice theory. His capability approach reframes development as expanding human freedoms rather than just growing GDP. Memex's policy agents use the capability lens to evaluate whether a proposed policy actually enlarges what real people can do and be—not just what aggregates measure.",
    historical_context: "Sen proved formally that no consistent social welfare function can satisfy Arrow's seemingly reasonable democratic criteria—extending Arrow's Impossibility Theorem in ways that reshaped welfare economics. He also demonstrated that famines are caused by failures of distribution and political accountability, not food scarcity—a finding that remains counterintuitive to the public but is now the consensus view among development economists and has directly shaped global food policy.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Amartya_Sen",
  },
  "Sachs": {
    cs_role: "Development Economist and Sustainable Development Architect",
    bio: "Jeffrey Sachs developed 'shock therapy' economic reform programmes for Bolivia and Eastern Europe, then became a leading advocate for sustainable development and global poverty reduction. Memex's policy agents draw on his evidence-based framework: quantify the problem precisely, identify binding constraints, and design targeted interventions with measurable feedback loops.",
    historical_context: "Sachs reduced Bolivia's hyperinflation from 23,000% to under 20% within months in 1985—a result so rapid the international community could barely track it. He later designed the UN Millennium Development Goals framework, credited with helping reduce extreme global poverty by more than half between 1990 and 2015. He has been both celebrated for ambitious targets and criticised for underestimating implementation complexity—a tension his own writing now engages directly.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Jeffrey_Sachs",
  },

  // ── Environmental perspective pool ─────────────────────────────────────────────
  "Carson": {
    cs_role: "Founder of the Modern Environmental Movement",
    bio: "Rachel Carson's 1962 book 'Silent Spring' documented the catastrophic environmental impact of DDT and other pesticides, directly triggering the modern environmental movement and the creation of the US EPA. Memex's environmental agents apply her precautionary methodology: when evidence of harm is credible and consequences potentially irreversible, the burden of proof lies with those deploying the technology, not those calling for caution.",
    historical_context: "Carson was dying of cancer while writing 'Silent Spring,' working in three-hour sessions between treatments. The chemical industry launched one of the most coordinated smear campaigns in American history against her—attacking her credentials, her gender, and her patriotism—a campaign that ultimately amplified public interest in the book rather than suppressing it. DDT was banned in the US in 1972.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Rachel_Carson",
  },
  "Attenborough": {
    cs_role: "Natural History Broadcaster and Conservation Advocate",
    bio: "David Attenborough's 70-year broadcasting career has introduced billions of people to the diversity of life on Earth and the threats facing it. Memex's environmental agents draw on his approach of grounding abstract ecological data in specific, observable, emotionally resonant stories—turning numbers into understanding that moves people.",
    historical_context: "Attenborough helped pioneer colour television at the BBC and was offered the role of Director-General—which he declined to continue making natural history films. His 2018 'Blue Planet II' episode on ocean plastic is credited with single-handedly shifting public opinion and triggering global legislative responses faster than any scientific paper or advocacy campaign had previously achieved.",
    wikipedia_url: "https://en.wikipedia.org/wiki/David_Attenborough",
  },
  "Lovins": {
    cs_role: "Soft Energy Paths Pioneer and Efficiency Economist",
    bio: "Amory Lovins pioneered the concept of 'soft energy paths'—arguing that investment in energy efficiency is cheaper, faster, and more reliable than building new power plants. Memex's environmental agents use his efficiency-first framework: before proposing any resource-intensive solution, quantify what could be achieved through smart conservation and better design first.",
    historical_context: "Lovins's 1976 Foreign Affairs article 'Energy Strategy: The Road Not Taken?' was so technically precise and economically compelling that it split American energy policy debate for a decade. He demonstrated that the entire US military's energy costs could be reduced by 90% through efficiency measures alone—a claim he then spent 30 years proving through actual Pentagon projects. He built his own house in the Rocky Mountains as a passive solar energy demonstration in 1984; it still exceeds its design targets.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Amory_Lovins",
  },

  // ── Social perspective pool ────────────────────────────────────────────────────
  "Du Bois": {
    cs_role: "Sociologist, Civil Rights Leader, and Data Visualisation Pioneer",
    bio: "W.E.B. Du Bois co-founded the NAACP, wrote 'The Souls of Black Folk,' and created groundbreaking hand-drawn data visualisations of Black American life for the 1900 Paris Exposition. Memex's social agents carry his insight that quantitative rigour and moral urgency are not opposites—the most powerful social analysis combines both.",
    historical_context: "Du Bois created infographics for the 1900 Paris Exposition—spiral charts, proportional area diagrams, and time-series graphs—that were not matched in visual sophistication by mainstream data journalism until the 21st century. He earned his PhD at Harvard in 1895, the first African-American to do so, and later studied at the Friedrich Wilhelm University in Berlin. He lived to 95, renounced his US citizenship, and moved to Ghana one day before the 1963 March on Washington.",
    wikipedia_url: "https://en.wikipedia.org/wiki/W._E._B._Du_Bois",
  },
  "Wollstonecraft": {
    cs_role: "Philosopher and Author of A Vindication of the Rights of Woman",
    bio: "Mary Wollstonecraft wrote 'A Vindication of the Rights of Woman' in 1792—the foundational text of modern feminism—arguing that women's apparent inferiority was a product of education and social structure, not nature. Memex's social agents apply her structural analysis: when a group consistently underperforms, examine the institutions and incentives before drawing conclusions about the group itself.",
    historical_context: "Wollstonecraft wrote the Vindication in just six weeks in 1791, in direct response to Edmund Burke's defence of tradition. She died at 38 from complications after giving birth to Mary Shelley—the author of Frankenstein. For over a century, her life was held up as a cautionary tale against female independence; the 20th-century feminist movement recovered her work and recognised it as the founding document of a civil rights movement.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Mary_Wollstonecraft",
  },
  "Bourdieu": {
    cs_role: "Sociologist of Power, Capital, and Social Reproduction",
    bio: "Pierre Bourdieu developed the concepts of social capital, cultural capital, and habitus—the invisible frameworks through which social inequality reproduces itself across generations. Memex's social agents apply his structural lens when analysing why outcomes are systematically distributed across social groups, looking beyond individual choices to the fields of power shaping them.",
    historical_context: "Bourdieu conducted his first major fieldwork in Algeria during the independence war, studying Kabyle society while serving as a conscript soldier—and turned his ethnographic notebooks into sociology. His concept of 'symbolic violence'—the process by which dominated groups come to see their domination as natural—is now applied in education research, corporate culture analysis, and the study of algorithmic discrimination in AI systems.",
    wikipedia_url: "https://en.wikipedia.org/wiki/Pierre_Bourdieu",
  },
};
