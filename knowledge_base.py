"""
Soccer coaching knowledge base built from publicly available coaching frameworks,
UEFA/USSF coaching manuals, and professional team tactical philosophies.
Used as placeholder data for the Tactify AI demo.
"""

POSITIONS = [
    "Goalkeeper (GK)",
    "Center-Back (CB)",
    "Right/Left Back (RB/LB)",
    "Defensive Midfielder (CDM)",
    "Central Midfielder (CM)",
    "Attacking Midfielder (CAM)",
    "Winger (RW/LW)",
    "Striker (ST)",
    "General / Not position-specific",
]

PLAY_TYPES = [
    "Attacking – Buildup Play",
    "Attacking – Final Third / Finishing",
    "Defending – Defensive Shape",
    "Defending – 1v1",
    "Transition – Pressing after losing ball",
    "Transition – Counter-attack",
    "Set Piece – Corner",
    "Set Piece – Free Kick",
    "Individual Technique – Dribbling",
    "Individual Technique – First Touch",
    "Individual Technique – Passing",
    "Individual Technique – Shooting",
]

AGE_GROUPS = [
    "Youth (U8–U12)",
    "Adolescent (U13–U17)",
    "Young Adult (U18–U23)",
    "Senior / Professional",
]

# -------------------------------------------------------------------
# KNOWLEDGE BASE
# Each entry: position or concept → techniques, common mistakes, drills,
# and professional team references
# -------------------------------------------------------------------

KNOWLEDGE_BASE = {
    "Goalkeeper (GK)": {
        "core_techniques": [
            "Set position: feet shoulder-width apart, weight on toes, hands at hip level",
            "Diving technique: lead with hand closest to ball, body behind it",
            "Distribution: short roll to CB, medium throw to fullback, long kick to switch play",
            "Sweeper-keeper: reading through balls and rushing to claim or clear",
            "Communication: constant verbal direction to the defensive line",
            "Footwork for crosses: early movement to claim or punch at highest point",
        ],
        "common_mistakes": [
            "Feet too wide on set position — reduces ability to push off laterally",
            "Hands too high — late adjustment to low shots",
            "Slow distribution — disrupts rhythm of buildup play",
            "Hesitating on crosses — neither claiming nor staying on line",
            "Parrying to dangerous areas instead of wide and safe",
        ],
        "recommended_drills": [
            "Reaction save series: coach shoots from short range at varying heights",
            "Cross claiming circuit: balls served from both wings, GK calls and claims",
            "Distribution accuracy: hitting targets at different distances",
            "Footwork ladder + immediate save: agility then shot-stopping",
            "1v1 angle closing: striker bears down, GK narrows angle",
        ],
        "pro_team_references": {
            "Manchester City": "Ederson exemplifies sweeper-keeper role — comfortable on the ball, aggressive at claiming balls behind the defensive line",
            "Liverpool": "Alisson's distribution triggers fast transitions; he initiates attacks with quick, precise throws",
            "Bayern Munich": "Neuer popularized the sweeper-keeper concept globally; reads through balls early and acts as an 11th outfield player",
        },
    },

    "Center-Back (CB)": {
        "core_techniques": [
            "Defending posture: side-on stance, jockeying to delay attacker",
            "Heading: attack the ball early, use forehead, direct toward wide areas",
            "Pressing trigger: step to ball when attacker's touch is heavy or head is down",
            "Cover shadow: position to block passing lane while pressuring",
            "Ball-playing: receive facing goal, drive forward or play through midfield",
            "Compactness: maintain 5–8 meter gap with midfield line, no daylight",
        ],
        "common_mistakes": [
            "Flat defensive line — easy to exploit with balls over the top",
            "Diving in during 1v1 instead of jockeying and delaying",
            "Watching the ball instead of tracking the runner",
            "Receiving with back to goal unnecessarily — loses time and creates pressure",
            "Communication breakdown when switching zones",
        ],
        "recommended_drills": [
            "1v1 defending — attacker runs at CB from 30 yards, CB jockeys to penalty area",
            "Shadow defending: CB mirrors attacker movement without ball, works on posture",
            "Aerial duel training: contested headers from various serve heights",
            "Playing out from the back: 3v2 or 4v3 scenarios pressing high",
            "Line coordination: back 4 walks and runs as a unit on coach's calls",
        ],
        "pro_team_references": {
            "Barcelona": "CBs like Piqué were expected to be composure under press and drive forward — they were the first pass of every build-up",
            "Atletico Madrid (Simeone)": "High aggression, compact block — CBs engage early and force play wide; minimal ball-playing risk taken",
            "Manchester City": "CBs step into midfield with the ball; Stones frequently inverted into a midfield role, creating numerical advantages",
        },
    },

    "Right/Left Back (RB/LB)": {
        "core_techniques": [
            "Overlapping run: timed run behind the winger to receive and cross",
            "Underlapping run: cutting inside behind the winger to overload half-space",
            "Crossing technique: driven low cross to near post, or cutback to penalty spot",
            "Defensive tracking: mirror the winger's movement, force to outside",
            "Positioning in possession: wide and high to stretch opponent's defensive shape",
            "Pressing coordination: trigger press in tandem with the winger above",
        ],
        "common_mistakes": [
            "Crossing from too deep — goalkeeper can easily claim",
            "Overlapping too early before winger is ready to receive",
            "Ball-watching in transition — winger escapes behind",
            "Square on stance when defending — easier to beat with pace",
            "Inverted run without awareness of cover — leaves space behind",
        ],
        "recommended_drills": [
            "Overlap and cross combination: winger holds, FB overlaps, first-time cross",
            "2v1 defending: fullback and CB coordinate to handle winger + striker",
            "Switching play receiving: CB plays diagonal ball to FB in space, FB crosses first time",
            "Tracking runner sessions: attacker makes run, FB shadow-defends without ball",
            "Set piece service: driven, in-swinging, and cutback deliveries from both sides",
        ],
        "pro_team_references": {
            "Manchester City (Pep Guardiola)": "Inverted fullbacks — Cancelo, Walker tuck into midfield rather than overlapping, creating a double-pivot with the CDM",
            "Liverpool (Klopp)": "Alexander-Arnold and Robertson make high, overlapping runs as a key attacking mechanism — often the team's most creative players",
            "Bayern Munich": "Davies and Mazraoui provide width and verticality; fullbacks are expected to win 1v1s offensively on both sides",
        },
    },

    "Defensive Midfielder (CDM)": {
        "core_techniques": [
            "Positioning: sit between the lines, behind midfield and ahead of the back 4",
            "Screening: position body in passing lane to block central passes",
            "Ball retention under pressure: shield ball with body, use backpass to reset",
            "Pressing trigger recognition: when to step and when to hold",
            "Transition: immediately track runners when possession is lost",
            "Switching play: receive, head up, play quickly to opposite side to change angle of attack",
        ],
        "common_mistakes": [
            "Being drawn out of position — chasing the ball instead of holding structure",
            "Poor angle of approach when pressing — attacker easily plays around",
            "Slow transition from attack to defense after losing ball",
            "Receiving square on — limits quick redistribution options",
            "Playing safe when there's space to progress into",
        ],
        "recommended_drills": [
            "Positional rondo: 6v2 or 8v3 — CDM role focuses on interceptions and positioning",
            "Pressing coordination: CDM steps on trigger, midfielders cover his zone",
            "Transition awareness: 5v5 — when team loses ball, CDM immediately drops to screen",
            "Long diagonal passing: switch play from side to side under pressure",
            "1v1 midfield duel: CDM presses attacker who receives from behind, must win ball",
        ],
        "pro_team_references": {
            "Barcelona (Xavi era)": "Busquets as CDM was the reference — minimal movement, maximum positional intelligence; always available between lines",
            "Atletico Madrid": "CDM role is combative and aggressive; Koke or Thomas Lemar responsible for disrupting opponent rhythm and winning second balls",
            "Real Madrid": "Casemiro exemplified combative CDM — aggressive press on trigger, immediate recovery run, shield back four",
        },
    },

    "Central Midfielder (CM)": {
        "core_techniques": [
            "Movement: constant repositioning to give teammate an outlet",
            "Box-to-box: contribute in both defensive and attacking phases",
            "Combination play: wall pass, third-man run, overlap triggers",
            "First touch direction: open body to receive, turn away from pressure",
            "Press coordination: coordinated press in pairs or triples with teammates",
            "Runs from deep: arriving late into the box on crosses",
        ],
        "common_mistakes": [
            "Static positioning — not creating passing angles for teammates",
            "Receiving facing own goal when space is available to turn",
            "Overcommitting to one phase (all attack or all defense)",
            "Poor timing of runs into the box — arriving too early or too late",
            "Ball-watching instead of making runs when wide players cross",
        ],
        "recommended_drills": [
            "Positional play 9v9 or 10v10 with zones — CM must operate across multiple areas",
            "Third man combination drills: A plays to B, B plays to C who has made run",
            "Box-to-box fitness + technique: long sprint, receive, pass, continue",
            "Small-sided press: 5v5, pair pressing triggers — CMs work together",
            "Late runs into box off crosses from fullback",
        ],
        "pro_team_references": {
            "Manchester City": "De Bruyne's movement and timing of runs from midfield is a global benchmark — creative, direct, and always a threat from distance",
            "Barcelona": "Pedri and Gavi exemplify pressing and ball retention in tight spaces; intense without losing technical quality",
            "Liverpool": "Midfielders like Thiago combined aggressive pressing with ability to control tempo — key to transition speed",
        },
    },

    "Attacking Midfielder (CAM)": {
        "core_techniques": [
            "Movement in tight spaces: turning on a dime, dribbling away from pressure",
            "Through ball weight and timing: playing balls between defensive lines",
            "Combination play: one-twos, layoffs, dribble to draw and release",
            "Pressing high: first line of press when team is out of possession",
            "Receiving between lines: half-turn body to view both options",
            "Shooting from range: quick-release on sight of goal",
        ],
        "common_mistakes": [
            "Standing still waiting for the ball — must constantly move to create angles",
            "Holding the ball too long in dangerous areas",
            "Not tracking back when team is out of possession",
            "Poor body position when receiving — back to goal with no turn available",
            "Over-dribbling in final third — one more dribble too many before shooting",
        ],
        "recommended_drills": [
            "Receiving between the lines + turn drill: bounce pass into CAM in tight space, must turn",
            "1-2-3 combination drill: short combination ending in shot",
            "High press trigger sessions: CAM and striker coordinate to press CB on back pass",
            "Finishing circuit: various angles, distances, service types",
            "Pocket receiving — back to goal, hold, turn or lay off",
        ],
        "pro_team_references": {
            "Real Madrid": "Modric and Kroos operated as dynamic CAMs capable of dictating tempo and creating from deep or advanced positions",
            "Manchester City": "Bernardo Silva and Phil Foden operate as high-energy CAMs — pressing and creating in equal measure",
            "PSG": "Mbappe and Dembélé demonstrate individual brilliance in the pocket — receiving, turning, and breaking lines at pace",
        },
    },

    "Winger (RW/LW)": {
        "core_techniques": [
            "1v1 dribbling: use of shoulder drop, step-over, and pace to beat fullback",
            "Cutting inside: inverted winger move to create shooting angle",
            "Crossing: early cross (before FB recovers), driven low, lofted, cutback",
            "Pressing: high intensity press from wide, force back toward center or sideline",
            "Width: stretching defensive shape, staying wide to create spaces centrally",
            "Support play: underlap for fullback overlap, combine in tight space",
        ],
        "common_mistakes": [
            "Going to ground in 1v1 — easier for defender to recover",
            "Crossing too early — ball comes in with defender in better position than attacker",
            "Predictable cuts — always going the same way",
            "Poor recovery run — walking back after losing possession",
            "Too narrow — not stretching the full-back, eliminating space for midfield",
        ],
        "recommended_drills": [
            "1v1 winger drill: winger receives from GK, beats fullback, crosses or shoots",
            "Crossing accuracy: driven and lofted deliveries to moving targets in the box",
            "Cutting inside + shoot: winger receives wide, cuts inside, shoots with strong foot",
            "Wide press: winger and fullback coordinate high press from wide position",
            "Combination wall pass with CM: winger combines, continues run for overlapping cross",
        ],
        "pro_team_references": {
            "Liverpool": "Salah (RW) exemplifies the inverted winger role — cuts inside consistently to shoot with his strong left foot, making him predictable but unstoppable",
            "Manchester City": "Bernardo Silva and Foden create overloads in half-spaces; width provided by fullbacks, not wingers — wingers stay central-ish",
            "Barcelona": "Wide forwards stay high and wide to stretch shape; primary role to create 1v1 and deliver quality balls into the box",
        },
    },

    "Striker (ST)": {
        "core_techniques": [
            "Movement off the ball: near-to-far runs, diagonal runs in behind, decoy movements",
            "Holding up play: back to goal, shield from CB, lay off to arriving midfielder",
            "Finishing: near post drive, far post placement, first-time finishes",
            "Pressing from front: force CB to play long or into trouble",
            "Aerial ability: timing the run, attack the ball at its highest point",
            "Link play: short combinations, flick-ons, and third-man triggers",
        ],
        "common_mistakes": [
            "Predictable runs — always straight, easily read by CB",
            "Poor touch direction on hold-up play — turning into pressure",
            "Over-running through balls — running past the ball",
            "Shooting across body when near post is open",
            "Not tracking back when team loses ball — leaves CB free",
        ],
        "recommended_drills": [
            "Movement + finish: striker starts behind cone, makes run on serve, finishes",
            "Holding up play: 2v2 with striker, back to goal, combinations with CM",
            "Pressing triggers: striker + CAM coordinate press on back 4",
            "Aerial finishing: various deliveries — striker attacks the ball in the air",
            "First-time finish circuit: quick combinations ending in striker's one-touch finish",
        ],
        "pro_team_references": {
            "Manchester City (Haaland)": "Pure goal-scoring movement — diagonal runs off the CB's shoulder, explosive first step, clinical near-post finishing",
            "Liverpool (Firmino)": "False 9 role — drops deep to involve in play, creates space for midfielders to arrive, pressing engine from front",
            "Real Madrid (Benzema)": "Complete striker — link play, movement, finishing; defines how a modern 9 operates in a possession system",
        },
    },

    "General / Not position-specific": {
        "core_techniques": [
            "First touch: cushion the ball, direct it away from pressure, toward space",
            "Passing technique: non-dominant foot training, through-ball weight, driven pass",
            "Defensive shape: team compactness, pressing in coordinated units",
            "Transition: immediate response to winning or losing possession",
            "Set pieces: rehearsed routines from corners, free kicks, and throw-ins",
        ],
        "common_mistakes": [
            "Poor body orientation when receiving — limits passing options",
            "Not scanning before receiving — reactive instead of proactive",
            "Losing individual defensive duels due to poor stance",
            "Wasting possession under low pressure",
            "Lack of urgency in defensive transitions",
        ],
        "recommended_drills": [
            "Rondo (all formats): 4v1, 5v2, 6v2 — emphasizes speed of play and positioning",
            "Shadow play: team moves through phases of attack without opposition",
            "Position-specific technical work: 20 minutes per session",
            "Small-sided games (SSG) with pressing triggers",
            "Set piece rehearsal: 15 minutes minimum per training session",
        ],
        "pro_team_references": {
            "Ajax": "Total Football philosophy — every player capable of playing any position; technical and tactical versatility is the foundation",
            "Barcelona (La Masia)": "Positional play (Juego de Posición): players learn to dominate spaces, not just positions — ball retention and numerical superiority",
            "Germany National Team": "Emphasis on high intensity pressing (gegenpressing) and vertical, direct transitions — physical and technical demands are both high",
        },
    },
}


def get_relevant_knowledge(position: str, play_type: str) -> str:
    """Build a context string from the knowledge base for the given position and play type."""
    kb = KNOWLEDGE_BASE.get(position, KNOWLEDGE_BASE["General / Not position-specific"])

    lines = []
    lines.append(f"=== POSITION: {position} ===\n")

    lines.append("CORE TECHNIQUES:")
    for t in kb["core_techniques"]:
        lines.append(f"  • {t}")

    lines.append("\nCOMMON MISTAKES TO LOOK FOR:")
    for m in kb["common_mistakes"]:
        lines.append(f"  • {m}")

    lines.append("\nRECOMMENDED DRILLS:")
    for d in kb["recommended_drills"]:
        lines.append(f"  • {d}")

    lines.append("\nPROFESSIONAL TEAM REFERENCES:")
    for team, ref in kb["pro_team_references"].items():
        lines.append(f"  [{team}] {ref}")

    lines.append(f"\n=== PLAY TYPE CONTEXT: {play_type} ===")
    lines.append(
        "Evaluate the footage specifically through the lens of this play type. "
        "Focus feedback on the technical and tactical elements most relevant to this situation."
    )

    return "\n".join(lines)
