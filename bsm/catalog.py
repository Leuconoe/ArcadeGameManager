from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class GameSignature:
    id: str
    title: str
    dlls: tuple[str, ...]
    aliases: tuple[str, ...]
    required_dlls: tuple[str, ...] = ()
    excluded_dlls: tuple[str, ...] = ()
    required_root_paths: tuple[str, ...] = ()


# Ordered from specific signatures to generic/ambiguous signatures.
GAME_SIGNATURES: tuple[GameSignature, ...] = (
    GameSignature("iidx", "beatmania IIDX", ("bm2dx.dll",), ("beatmania iidx", "iidx")),
    GameSignature("sdvx", "SOUND VOLTEX", ("soundvoltex.dll",), ("sound voltex", "sdvx")),
    GameSignature("jubeat", "jubeat", ("jubeat.dll", "jubeat2019.dll"), ("jubeat", "jb")),
    GameSignature("reflecbeat", "REFLEC BEAT", ("reflecbeat.dll",), ("reflec beat", "reflecbeat", "rb")),
    GameSignature("beatstream", "BeatStream", ("beatstream.dll",), ("beatstream", "bs")),
    GameSignature("museca", "MÚSECA", ("museca.dll",), ("museca",)),
    GameSignature("popn-modern", "pop'n music", ("popn22.dll",), ("pop'n music", "popn")),
    GameSignature("popn-21", "pop'n music", ("popn21.dll",), ("pop'n music", "popn")),
    GameSignature("popn-20", "pop'n music", ("popn20.dll",), ("pop'n music", "popn")),
    GameSignature("popn-19", "pop'n music", ("popn19.dll",), ("pop'n music", "popn")),
    GameSignature("popn-pika", "pop'n music", ("popn.dll",), ("pop'n music", "popn"), required_dlls=("libaio-iob2_video.dll",)),
    GameSignature("hello-popn", "HELLO! pop'n music", ("popn.dll",), ("hello popn", "hello pop'n"), excluded_dlls=("libaio-iob2_video.dll",)),
    GameSignature("ddr", "DanceDanceRevolution", ("arkmdxbio2.dll", "arkmdxp3.dll", "arkmdxp4.dll", "mdxja_945.dll", "mdxja_hm65.dll", "ddr.dll"), ("dancedancerevolution", "dance dance revolution", "ddr")),
    GameSignature("gitadora", "GITADORA", ("gdxg.dll",), ("gitadora", "gdxg")),
    GameSignature("nostalgia", "NOSTALGIA", ("nostalgia.dll",), ("nostalgia",)),
    GameSignature("dancerush", "DANCERUSH STARDOM", ("superstep.dll",), ("dancerush stardom", "dancerush", "drs")),
    GameSignature("bishi-bashi", "Bishi Bashi Channel", ("bsch.dll",), ("bishi bashi channel", "bishi bashi", "bbc")),
    GameSignature("qma", "Quiz Magic Academy", ("client.dll",), ("quiz magic academy", "qma")),
    GameSignature("dance-evolution", "DanceEvolution ARCADE", ("arkkdm.dll",), ("dance evolution", "danceevolution", "dea")),
    GameSignature("loveplus", "LovePlus", ("arkklp.dll",), ("loveplus", "love plus")),
    GameSignature("steel-chronicle", "Steel Chronicle", ("arkkgg.dll",), ("steel chronicle",)),
    GameSignature("future-tomtom", "FutureTomTom", ("arkmmd.dll",), ("futuretomtom", "future tomtom")),
    GameSignature("scotto", "Scotto", ("scotto.dll",), ("scotto",)),
    GameSignature("otoca", "Otoca D'or", ("arkkep.dll",), ("otoca", "otoca d'or")),
    GameSignature("silent-scope", "Silent Scope: Bone Eater", ("arkndd.dll",), ("silent scope",)),
    GameSignature("ongaku-paradise", "Ongaku Paradise", ("arkjc9.dll",), ("ongaku paradise",)),
    GameSignature("winning-eleven", "Winning Eleven", ("weac12_bootstrap_release.dll", "arknck.dll"), ("winning eleven", "we")),
    GameSignature("road-fighters-3d", "Road Fighters 3D", ("jgt.dll",), ("road fighters", "rf3d")),
    GameSignature("shogikai", "Shogi", ("shogi_engine.dll",), ("shogi",)),
    GameSignature("mga", "MGA", ("launch.dll",), ("mga",), required_dlls=("ess.dll",)),
    GameSignature("pcm", "PCM", ("launch.dll",), ("pcm",), excluded_dlls=("ess.dll",)),
    GameSignature("mfc", "Mahjong Fight Club", ("allinone.dll",), ("mahjong fight club", "mfc")),
    GameSignature("mfc", "Mahjong Fight Club", ("system.dll",), ("mahjong fight club", "mfc"), required_root_paths=("data/mfc.ini",)),
    GameSignature("chase-chase-jokers", "Chase Chase Jokers", ("kamunity.dll",), ("chase chase jokers", "ccj"), required_root_paths=("game/chaseproject.exe",)),
    GameSignature("quizknock", "QuizKnock STADIUM", ("kamunity.dll",), ("quizknock stadium", "quizknock", "qks"), required_root_paths=("game/uks.exe",)),
    GameSignature("mahjong-fight-girl", "Mahjong Fight Girl", ("kamunity.dll",), ("mahjong fight girl", "mfg"), required_root_paths=("game/MFGClient_Data",)),
    GameSignature("polaris-chord", "Polaris Chord", ("kamunity.dll",), ("polaris chord",), required_root_paths=("game/svm.exe",)),
    GameSignature("battle-conductor", "Busou Shinki: Battle Conductor", ("kamunity.dll",), ("battle conductor", "busou shinki"), required_root_paths=("game/bsac_app.exe",)),
)


SIGNATURE_BY_ID = {signature.id: signature for signature in GAME_SIGNATURES}


def catalog_titles() -> dict[str, str]:
    result: dict[str, str] = {}
    for signature in GAME_SIGNATURES:
        result.setdefault(signature.id, signature.title)
    return result
