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
};
