# Mapping of normalized text/intents to relative paths in agents/bmo_voice/voice_samples
# Keys should be lowercased and stripped of punctuation for better matching

VOICE_SAMPLES_MAP = {
    # Intro / Greetings
    "hello": "Intro02_Hello_ItsMeBEEMO.wav",
    "hi": "Intro02_Hello_ItsMeBEEMO.wav",
    "hello there": "Intro02_Hello_ItsMeBEEMO.wav",
    "hello its me beemo": "Intro02_Hello_ItsMeBEEMO.wav",
    "its beemo time": "Intro06_Its_beemo_Time.wav",
    
    # Emotional / Reactions
    "ouch": "Ouch.wav",
    "whoa": "Whoa.wav",
    "whee": "Whee.wav",
    "yay": "Whee_2.wav",
    "hahaha": "Giggle01.wav",
    "haha": "Giggle01.wav",
    "giggle": "Giggle01.wav",
    "smile": "Smile.wav",
    "angry": "Angry.wav",
    "frown": "Frown.wav",
    
    # Games
    "who wants to play video games": "General_Games01_whoWantsToPlayVideoGames.wav",
    "i made this just for you": "General_Games02_madeThisJustForYou.wav",
    "that was awesome": "General_Games11_thatWasAWESOME.wav",
    "poneage": "General_Games29_PONEAGE.wav",
    "game over": "Player_Lose09_GAMEOVER.wav",
    "victory": "Player_Win07_VICTORY.wav",
    "you win": "Player_Win02_youWin.wav",
    "i win": "Player_Lose01_iWin.wav",
    "beemo wins": "Player_Lose02_beemoWins.wav",
    "congratulations": "Player_Win06_congratulations.wav",
    "nice job": "Player_Win04_NiceJob.wav",
    "do you want to play again": "Player_Win09_DoYouWantToPLayAgain.wav",
    "lets play": "Game_Select09_Lets_Play.wav",
    "total domination": "Player_Lose05_TotalDomination.wav",
    "better luck next time": "Player_Lose06_betterLuckNextTime.wav",
    
    # Interaction
    "make a choice": "Other18_makeAChoice.wav",
    "touch your choice": "Other19_touchYourChoice.wav",
    "word": "Other03_word.wav",
    "boop boop": "Other06_1_boopBoop.wav",
    
    # Poking / Touching
    "ow": "Poke01_2_owww2.wav",
    "my face": "Poke05_MyFace.wav",
    "be gentle": "Poke06_BeGentle.wav",
    "knock it off": "Poke07_knockItOff.wav",
    "why are you poking": "Poke08_whyAreYouPoking.wav",
    
    # Shaking
    "that was fun": "Shake04_thatWasFun.wav",
    "dancing machine": "Shake05_DancingMachine.wav",
    "dont shake me": "Shake09_pleaseStopShakingBeemo.wav",
    "easy on the merch": "Shake07_easyOnTheMerch.wav",
    
    # Tickling
    "that tickles": "Tickle01_ThatTickles1.wav",
    "cut that out": "Tickle05_cutThatOut.wav",
    "too much tickling": "Tickle06_tooMuchTickling.wav",
    
    # Camera
    "camera": "Camera01_camera.wav",
    "beemo is camera": "Camera02_beemoIsCamera.wav",
    
    # Conversation Starters / Fillers (for streaming pipeline latency hiding)
    "hmm": "Conversation_Parade_Interested01.wav",
    "hmm let me think": "Conversation_Parade_Interested01.wav",
    "interesting": "Conversation_Parade_Interested01.wav",
    "oh": "Conversation_Parade_Interested01.wav",
    "well": "Conversation_Parade_Starter01.wav",
    "so": "Conversation_Parade_Starter01.wav",
    "good morning": "Conversation_Parade_Wake01.wav",
    "wake up": "Conversation_Parade_Wake01.wav",
    "good night": "Conversation_Parade_Sleep01.wav",
    "sweet dreams": "Conversation_Parade_Sleep01.wav",
    "im bored": "Conversation_Parade_Bored01.wav",
    "whatever": "Conversation_Parade_Random01.wav",
}

def get_sample_path(text: str) -> str | None:
    """
    Checks if the input text exactly matches a pre-recorded sample.
    Returns the filename if found, otherwise None.
    """
    import re
    # Normalize: lowercase, remove non-alphanumeric (keep spaces)
    normalized = re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()
    return VOICE_SAMPLES_MAP.get(normalized)


def find_sample_in_response(text: str) -> str | None:
    """
    Scans the text for any known multi-word sample phrase embedded within it.
    Only matches phrases with 3+ words to avoid single-word interjections
    like 'whoa' or 'ow' replacing full TTS responses.
    """
    import re
    MIN_WORDS = 3  # 'who wants to play video games' = match; 'whoa' = skip
    normalized = re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()
    
    best_match = None
    best_len = 0
    for phrase, filename in VOICE_SAMPLES_MAP.items():
        if len(phrase.split()) < MIN_WORDS:
            continue  # Skip short interjections
        pattern = r'\b' + re.escape(phrase) + r'\b'
        if re.search(pattern, normalized) and len(phrase) > best_len:
            best_match = filename
            best_len = len(phrase)
    
    return best_match


# Canonical phrases the LLM should use to trigger samples
SAMPLE_PHRASES = list(VOICE_SAMPLES_MAP.keys())
