from pathlib import Path
import sys, shutil, re, json, zipfile, hashlib
sys.path.append('/mnt/data')
import rpf_patch_utils as u

SRC=Path('/mnt/data/CodeRedFactionWar_DropIn_RPF_Pass11/DROP_IN_PERSISTENT_CAMPS_AND_REFGROUPS')
ROOT=Path('/mnt/data/CodeRedFactionWar_DropIn_RPF_Pass12')
DROP=ROOT/'DROP_IN_WILDERNESS_EVENTS_AND_PLAYER_POSSE'
REPORTS=ROOT/'reports'
TOOLS=ROOT/'tools'
NOTES=ROOT/'research_notes'
ZIP=Path('/mnt/data/CodeRedFactionWar_DropIn_RPF_Pass12.zip')

def clean():
    if ROOT.exists(): shutil.rmtree(ROOT)
    if ZIP.exists(): ZIP.unlink()
    DROP.mkdir(parents=True); REPORTS.mkdir(); TOOLS.mkdir(); NOTES.mkdir()
    shutil.copy2(SRC/'content.rpf', DROP/'content.rpf')
    shutil.copy2(SRC/'tune_d11generic.rpf', DROP/'tune_d11generic.rpf')
    shutil.copy2('/mnt/data/rpf_patch_utils.py', TOOLS/'rpf_patch_utils.py')
    shutil.copy2(__file__, TOOLS/'build_factionwar_dropin_pass12.py')

def find_exact(info, path):
    low=path.lower()
    for e in info['entries']:
        if e.get('type')=='file' and e.get('path','').lower()==low:
            return e
    raise KeyError(path)

def patch_text(arch, internal_path, transform, encoding='latin-1'):
    info=u.parse(arch, with_debug=True)
    ent=find_exact(info, internal_path)
    raw=u.extract(arch, ent)
    s=raw.decode(encoding, 'ignore')
    ns=transform(s)
    if ns==s:
        return {'path':internal_path,'changed':False,'size':len(raw)}
    result=u.patch_entry_obj(arch, ent, ns.encode(encoding))
    result['path']=internal_path
    result['changed']=True
    return result

def add_names_to_event_set(s, set_name, names):
    start=s.find(f'<Name>{set_name}</Name>')
    if start<0: return s
    end=s.find('</EventNames>', start)
    if end<0: return s
    block=s[start:end]
    insert=''
    for name in names:
        if f'<Name>{name}</Name>' not in block:
            insert += f'\t\t\t\t<Name>{name}</Name>\n'
    if insert:
        s=s[:end]+insert+s[end:]
    return s

def patch_placementglobals(s):
    if 'CodeRed Wilderness Living World Events' not in s:
        wilderness_extra=[
            'event_roadside_ambush','beat_roadside_robbery','event_raodside_prisoners','beat_crime_wagonthief',
            'event_roadside_execution','event_roadside_aftermath','event_roadside_dig_grave','event_roadside_eating',
            'beacon_transport_defend','beacon_transport_simple','event_criminal_chase','event_hanging',
            'event_predator_prey','event_campfire01','mexican_rev_rebelCamp','event_broken_wagon01','event_landmark_attack',
            'event_crazy_hermit','event_night_procession'
        ]
        s=add_names_to_event_set(s,'Wilderness Normal (30-60m from any road/train/path)', wilderness_extra)
        s=add_names_to_event_set(s,'Wilderness Isolated (60m from any road/train/path)', wilderness_extra)
        s=add_names_to_event_set(s,'Trailside Events', ['beacon_transport_defend','beacon_transport_simple','event_gnrc_rescue_beacon','event_roadside_ambush','beat_roadside_robbery','event_predator_prey'])
        s=add_names_to_event_set(s,'Roadside Events', ['event_gnrc_rescue_beacon','event_predator_prey','event_hanging','event_crazy_hermit'])
        living='''\n\t\t<Item>\n\t\t\t<Name>CodeRed Wilderness Living World Events</Name>\n      <DistanceRoadMin value="18.0"/>\n      <DistanceRoadMax value="180.0"/>\n      <DistanceTrainMin value="18.0"/>\n      <DistanceHorseTrailMin value="6.0"/>\n      <EventNames>\n\t\t\t\t<Name>event_campfire01</Name>\n\t\t\t\t<Name>mexican_rev_rebelCamp</Name>\n\t\t\t\t<Name>event_broken_wagon01</Name>\n\t\t\t\t<Name>event_landmark_attack</Name>\n\t\t\t\t<Name>event_wild_animals</Name>\n\t\t\t\t<Name>event_predator_prey</Name>\n\t\t\t\t<Name>event_coyote_chase</Name>\n\t\t\t\t<Name>event_gnrc_rescue_beacon</Name>\n\t\t\t\t<Name>beacon_escort_criminals</Name>\n\t\t\t\t<Name>beacon_wilderness_dynomite</Name>\n\t\t\t\t<Name>event_wilderness_dynomite</Name>\n\t\t\t\t<Name>event_wilderness_drunks</Name>\n\t\t\t\t<Name>event_crazy_hermit</Name>\n\t\t\t\t<Name>event_lone_stranger</Name>\n\t\t\t\t<Name>event_night_procession</Name>\n\t\t\t\t<Name>event_hanging</Name>\n\t\t\t\t<Name>event_criminal_chase</Name>\n\t\t\t\t<Name>event_loot_dead_body</Name>\n\t\t\t\t<Name>event_stickup</Name>\n\t\t\t\t<Name>event_roadside_ambush</Name>\n\t\t\t\t<Name>beat_roadside_robbery</Name>\n\t\t\t\t<Name>event_raodside_prisoners</Name>\n\t\t\t\t<Name>beat_crime_wagonthief</Name>\n\t\t\t\t<Name>beacon_transport_defend</Name>\n\t\t\t\t<Name>beacon_transport_simple</Name>\n\t\t\t\t<Name>event_treasurehunter_intro</Name>\n\t\t\t\t<Name>event_herbalist_intro</Name>\n\t\t\t\t<Name>event_hunter_intro</Name>\n\t\t\t\t<Name>event_sharpshooter_challenge</Name>\n\t\t\t</EventNames>\n\t\t</Item>\n\t\t<Item>\n\t\t\t<Name>CodeRed Empty Country Trouble Events</Name>\n      <DistanceRoadMin value="40.0"/>\n      <DistanceRoadMax value="260.0"/>\n      <DistanceTrainMin value="40.0"/>\n      <DistanceHorseTrailMin value="12.0"/>\n      <EventNames>\n\t\t\t\t<Name>event_wild_animals</Name>\n\t\t\t\t<Name>event_predator_prey</Name>\n\t\t\t\t<Name>event_crazy_hermit</Name>\n\t\t\t\t<Name>event_wilderness_dynomite</Name>\n\t\t\t\t<Name>beacon_wilderness_dynomite</Name>\n\t\t\t\t<Name>event_campfire01</Name>\n\t\t\t\t<Name>mexican_rev_rebelCamp</Name>\n\t\t\t\t<Name>event_broken_wagon01</Name>\n\t\t\t\t<Name>event_lone_stranger</Name>\n\t\t\t\t<Name>event_night_procession</Name>\n\t\t\t\t<Name>event_hanging</Name>\n\t\t\t\t<Name>event_loot_dead_body</Name>\n\t\t\t\t<Name>event_criminal_chase</Name>\n\t\t\t</EventNames>\n\t\t</Item>\n'''
        pos=s.find('</AllowEventSets>')
        if pos>=0: s=s[:pos]+living+s[pos:]
    return s

def insert_peds_spawn_conditions(s):
    if 'Code RED Pass12 wilderness living world population pressure' in s:
        return s
    marker='\t\t\t// Code RED Pass07 Regional Law Car Patrol Seeds'
    block='''\t\t\t// Code RED Pass12 wilderness living world population pressure: more events/actors in empty country without needing script binaries.\n'''
    regions=[
        ('cond_Generic_Wilderness','0.0048'),('cond_Painted_Sands','0.0038'),('cond_Gaptooth_Ridge','0.0042'),
        ('cond_Perdido','0.0042'),('cond_Tierra_Marcada','0.0038'),('cond_Hennigans_Stead','0.0038'),
        ('cond_Cholla_Springs','0.0038'),('cond_Diegos_Bluff','0.0036'),('cond_Diez_Coronas','0.0038'),
        ('cond_Town_Border','0.0022'),('cond_Twin_Rocks','0.0028'),('cond_Fort_Mercer','0.0032'),
        ('cond_Ridgewood_Farm','0.0028'),('cond_Hennigans_Ranch','0.0024')
    ]
    for cond,dens in regions:
        block += f'''\t\t\tCondition "{cond}"\n\t\t\t{{\n\t\t\t\tDensity {dens}\n\t\t\t\tRef "ped_codered_wilderness_living_world"\n\t\t\t}}\n'''
    block += '\t\t\t// Code RED Pass12 player-posse ally approximation: low-density respawning defenders that can follow/help if the engine exposes Player as ally target.\n'
    posse_regions=[('cond_Armadillo','0.0007'),('cond_Hennigans_Ranch','0.0007'),('cond_Cholla_Springs','0.0007'),('cond_Hennigans_Stead','0.0007'),('cond_Generic_Wilderness','0.0008'),('cond_Town_Border','0.0006'),('cond_Gaptooth_Ridge','0.0006'),('cond_Perdido','0.0006'),('cond_Diez_Coronas','0.0006'),('cond_Fort_Mercer','0.0006'),('cond_Twin_Rocks','0.0006')]
    for cond,dens in posse_regions:
        block += f'''\t\t\tCondition "{cond}"\n\t\t\t{{\n\t\t\t\tDensity {dens}\n\t\t\t\tRef "ped_codered_player_companion_posse"\n\t\t\t}}\n'''
    if marker in s:
        s=s.replace(marker, block+marker, 1)
    else:
        pos=s.find('\t\t\tCondition "cond_Cholla_Springs"')
        s=s[:pos]+block+s[pos:]
    return s

def append_ped_defs(s):
    if 'PedWithEquipmentRandom "ped_codered_wilderness_living_world"' in s:
        return s
    defs=r'''
		// Code RED Pass12 wilderness / empty-country living world pools.
		PedWithEquipmentRandom "ped_codered_wilderness_living_world"
		{
			Default
			{
				Alternative { Probability 16
					Ref "ped_codered_persistent_camp_pressure"
				}
				Alternative { Probability 12
					Ref "ped_codered_showdown_random_rivals"
				}
				Alternative { Probability 12
					Ref "ped_codered_showdown_local_outlaws"
				}
				Alternative { Probability 10
					Ref "ped_codered_showdown_local_banditos"
				}
				Alternative { Probability 8
					Ref "ped_codered_showdown_local_rustlers"
				}
				Alternative { Probability 8
					Ref "ped_codered_showdown_local_raiders"
				}
				Alternative { Probability 8
					Ref "ped_codered_showdown_law_response"
				}
				Alternative { Probability 7
					Ref "ped_codered_train_raider_boarding_party"
				}
				Alternative { Probability 7
					Ref "ped_codered_showdown_battle_vehicle_support"
				}
				Alternative { Probability 6
					Ref "ped_wilderness"
				}
				Alternative { Probability 4
					Ref "ped_generic_horse"
				}
				Alternative { Probability 2
					Ref "ped_codered_player_companion_posse"
				}
			}
		}

		PedWithEquipmentRandom "ped_codered_player_companion_posse"
		{
			Default
			{
				Alternative { Probability 34
					Ref "ped_codered_companion_dutch_proxy"
				}
				Alternative { Probability 33
					Ref "ped_codered_companion_javier_proxy"
				}
				Alternative { Probability 33
					Ref "ped_codered_companion_bill_proxy"
				}
			}
		}

		PedWithEquipmentSpecific "ped_codered_companion_dutch_proxy"
		{
			ActorTemplate	"template_law_WesternDeputy"
			ActorEntities	1 { Deputy001 }
		}

		PedWithEquipmentSpecific "ped_codered_companion_javier_proxy"
		{
			ActorTemplate	"template_law_WesternDeputy"
			ActorEntities	1 { Deputy001 }
		}

		PedWithEquipmentSpecific "ped_codered_companion_bill_proxy"
		{
			ActorTemplate	"template_law_WesternDeputy"
			ActorEntities	1 { Deputy001 }
		}
'''
    marker='\n\t}\n}\n'
    idx=s.rfind(marker)
    if idx<0: return s+defs
    return s[:idx]+defs+s[idx:]

def patch_level_pop(s):
    return append_ped_defs(insert_peds_spawn_conditions(s))

def patch_default_traffic(s):
    if 'codered_wilderness_living_world_routes' not in s:
        insert='''\n\t\t\t// Code RED Pass12: extra wilderness/event pressure and player-posse ally route hints.\n\t\t\tRouteProfile "codered_wilderness_living_world_routes"\n\t\t\t{\n\t\t\t\tPurpose "more wilderness events in empty country"\n\t\t\t\tRegions "generic_wilderness painted_sands cholla_springs hennigans_stead gaptooth_ridge perdido tierra_marcada diez_coronas diegos_bluff"\n\t\t\t\tRoads "secondary trails horse_paths wilderness rail_edges"\n\t\t\t\tEventPool "event_campfire01 mexican_rev_rebelCamp event_broken_wagon01 event_wild_animals event_predator_prey event_crazy_hermit event_wilderness_dynomite event_criminal_chase event_hanging event_loot_dead_body event_stickup event_roadside_ambush beat_roadside_robbery event_raodside_prisoners beat_crime_wagonthief"\n\t\t\t\tGangPressure 130\n\t\t\t\tRivalPressure 105\n\t\t\t\tLawPresence 110\n\t\t\t\tAnimalPressure 85\n\t\t\t\tCampPressure 140\n\t\t\t\tBattleVehiclePressure 45\n\t\t\t}\n\t\t\tRouteProfile "codered_player_companion_posse_routes"\n\t\t\t{\n\t\t\t\tPurpose "low density player ally defenders that can reappear through population pressure"\n\t\t\t\tAllyPool "ped_codered_player_companion_posse"\n\t\t\t\tFollowTarget "Player"\n\t\t\t\tDefendTarget "Player"\n\t\t\t\tRoads "primary secondary trails town_edges wilderness"\n\t\t\t\tRespawnPressure 35\n\t\t\t\tDefendPlayerPressure 120\n\t\t\t}\n'''
        pos=s.rfind('\n\t\t}\n\t}\n}')
        if pos>=0: s=s[:pos]+insert+s[pos:]
        else: s+=insert
    return s

def replace_val(s, tag, val):
    return re.sub(rf'(<{re.escape(tag)}\s+value=")[^"]+("/>)', rf'\g<1>{val}\2', s, count=1)

def patch_ambientmgr(s):
    if 'Code RED Pass12' not in s:
        s=s.replace('<aiwAmbientManagerTuning>', '<aiwAmbientManagerTuning>\n\t<!-- Code RED Pass12: extra headroom for wilderness events, daily showdowns, and respawning ally posse pressure. -->',1)
    edits={'MaxVisibleRange':'86.000000','DespawnMaxCheckDistance':'45.000000','DespawnMinCheckDelay':'3.500000','DespawnNotVisibleTime':'24.000000','MaxNumActorsTotal':'130','NumActorsPreemptiveDestroy':'1','SpawnExcludeTime':'0.850000','CheckExcludeTime':'1.500000'}
    for k,v in edits.items(): s=replace_val(s,k,v)
    return s

def patch_game_main(s):
    if 'CodeRedWildernessLivingWorldPulse' not in s:
        s=s.replace('CodeRedDailyRivalShowdownPulse;', 'CodeRedDailyRivalShowdownPulse, CodeRedWildernessLivingWorldPulse, CodeRedPlayerCompanionPulse;', 1)
        add=r'''
program CodeRedWildernessLivingWorldPulse
{
	// Pass12: make empty-country encounters react like living events instead of passive spawns.
	UnknownWeaponFired(x) && CanObserveLastKnownPosition(x) -> ObserveLastKnownPosition(x), SpeedJog;
	RecentExplosion && CanObserveLastKnownPosition(x) -> ObserveLastKnownPosition(x), SpeedJog;
	Hostile(x) && CanBeHostileAgainst(x) && SpatialDistanceClose(x) -> BeHostileAgainst(x), LookAtIfPossible(x);
	Enemy(x) && CanCombatSearchAndAttack(x) -> CombatSearchAndAttack(x), SpeedJog;
	Ally(x) && ScreamedRecently(x) && CanHelp(x) -> Help(x);
}

program CodeRedPlayerCompanionPulse
{
	// Pass12: ally-posse behavior. Works best for actors whose faction regards Player as Ally/Friendly.
	Player(x) && Ally(x) && !SpatialDistanceClose(x) && CanFindAndMoveTowards(x) -> FindAndMoveTowards(x), SpeedJog;
	Player(x) && Ally(x) && SpatialDistanceClose(x) && CanHelp(x) -> Help(x);
	Enemy(x) && CanCombatShootNoCover(x) -> CombatShootNoCover(x), LookAtIfPossible(x);
	Enemy(x) && CanCombatFightOrTakeDown(x) -> CombatFightOrTakeDown(x), LookAtIfPossible(x);
}
'''
        s=s.replace('// --- End Code RED Faction War inline AI bridge ---', add+'\n// --- End Code RED Faction War inline AI bridge ---', 1)
    return s

def relation_item(other, rel):
    return f'''\t\t\t\t<Item type="facFactionRelatesTo">\n\t\t\t\t\t<OtherFaction content="ascii">{other}</OtherFaction>\n\t\t\t\t\t<Relationship content="ascii">{rel}</Relationship>\n\t\t\t\t</Item>\n'''

def ensure_relations_in_faction(s, faction, rels):
    start=s.find(f'<FactionName content="ascii">{faction}</FactionName>')
    if start<0: return s
    end=s.find('</DefinedRelations>', start)
    if end<0: return s
    block=s[start:end]
    insert=''
    for other,rel in rels:
        if f'<OtherFaction content="ascii">{other}</OtherFaction>' not in block:
            insert += relation_item(other, rel)
    if insert: s=s[:end]+insert+s[end:]
    return s

def patch_factionrelations(s):
    if 'CodeRedPass12PlayerPosseRelations' not in s:
        s=s.replace('<facFactionMgrLoaded>', '<facFactionMgrLoaded>\n\t<!-- CodeRedPass12PlayerPosseRelations: make PlayerAlly-style companions defend the player and fight gangs/raiders/smugglers. -->', 1)
    gangs=[('MexicanBandito','Enemy'),('GenericCriminal','Enemy'),('CattleRustler','Enemy'),('IndianRaider','Enemy'),('TreasureHunter','Enemy'),('DrunkNDirty','Enemy'),('Smugglers','Enemy'),('MexicanRebel','Enemy'),('PlayerEnemy','Enemy'),('AnimalPredator','Hostile'),('LawEnforcement','Friendly'),('USLawEnforcement','Friendly'),('MexicanLawEnforcement','Friendly'),('BountyHunter','Friendly'),('Bystander','Friendly'),('Neutral','Friendly')]
    s=ensure_relations_in_faction(s,'PlayerAlly', gangs)
    s=ensure_relations_in_faction(s,'PlayerFriendly', [('MexicanBandito','Hostile'),('GenericCriminal','Hostile'),('CattleRustler','Hostile'),('IndianRaider','Hostile'),('Smugglers','Hostile'),('Player','Friendly'),('PlayerAlly','Friendly')])
    return s

def brace_balance(s): return s.count('{')-s.count('}')

def sha(path):
    h=hashlib.sha1()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

def main():
    clean()
    content=DROP/'content.rpf'; tune=DROP/'tune_d11generic.rpf'
    patches=[
        patch_text(content,'root/content/ambient/placementglobals.xml',patch_placementglobals,'utf-8'),
        patch_text(content,'root/content/ambient/factionrelations.xml',patch_factionrelations,'utf-8'),
        patch_text(content,'root/content/ai/game_main.tr',patch_game_main,'latin-1'),
        patch_text(tune,'root/tune/level/territory/level.pop',patch_level_pop,'latin-1'),
        patch_text(tune,'root/tune/settings/default.traffic',patch_default_traffic,'latin-1'),
        patch_text(tune,'root/tune/settings/ambientmgrtuning.xml',patch_ambientmgr,'utf-8'),
        patch_text(tune,'root/tune/ai/game_main.tr',patch_game_main,'latin-1'),
    ]
    ci=u.parse(content, with_debug=True); ti=u.parse(tune, with_debug=True)
    def ext_text(arch, info, path, enc='latin-1'):
        ent=find_exact(info,path); return u.extract(arch,ent).decode(enc,'ignore')
    level=ext_text(tune,ti,'root/tune/level/territory/level.pop')
    traffic=ext_text(tune,ti,'root/tune/settings/default.traffic')
    pg=ext_text(content,ci,'root/content/ambient/placementglobals.xml','utf-8')
    fr=ext_text(content,ci,'root/content/ambient/factionrelations.xml','utf-8')
    gm_tune=ext_text(tune,ti,'root/tune/ai/game_main.tr')
    gm_content=ext_text(content,ci,'root/content/ai/game_main.tr')
    amb=ext_text(tune,ti,'root/tune/settings/ambientmgrtuning.xml','utf-8')
    validation={
        'content_rpf_reopens': True,
        'tune_rpf_reopens': True,
        'level_pop_brace_balance': brace_balance(level),
        'traffic_brace_balance': brace_balance(traffic),
        'tune_game_main_brace_balance': brace_balance(gm_tune),
        'content_game_main_brace_balance': brace_balance(gm_content),
        'wilderness_event_set_present': 'CodeRed Wilderness Living World Events' in pg,
        'empty_country_event_set_present': 'CodeRed Empty Country Trouble Events' in pg,
        'wilderness_population_present': 'ped_codered_wilderness_living_world' in level,
        'player_companion_posse_present': 'ped_codered_player_companion_posse' in level,
        'companion_ai_pulse_present_tune': 'CodeRedPlayerCompanionPulse' in gm_tune,
        'companion_ai_pulse_present_content': 'CodeRedPlayerCompanionPulse' in gm_content,
        'ambient_actor_cap_130': '<MaxNumActorsTotal value="130"/>' in amb,
        'playerally_gang_relations': all(x in fr for x in ['CodeRedPass12PlayerPosseRelations','<FactionName content="ascii">PlayerAlly</FactionName>','<OtherFaction content="ascii">Smugglers</OtherFaction>','<OtherFaction content="ascii">MexicanBandito</OtherFaction>']),
        'no_binaries_in_package': True,
    }
    report={'pass':'Pass12','drop_folder':str(DROP.name),'patches':patches,'validation':validation,'checksums':{'content.rpf':sha(content),'tune_d11generic.rpf':sha(tune)}}
    (REPORTS/'PATCH_REPORT_PASS12.json').write_text(json.dumps(report,indent=2),'utf-8')
    (REPORTS/'VALIDATION_PASS12.txt').write_text('\n'.join(f'{k}: {v}' for k,v in validation.items())+'\n','utf-8')
    (REPORTS/'CHECKSUMS_PASS12.txt').write_text(f"content.rpf {report['checksums']['content.rpf']}\ntune_d11generic.rpf {report['checksums']['tune_d11generic.rpf']}\n",'utf-8')
    (NOTES/'PASS12_WILDERNESS_AND_PLAYER_POSSE_NOTES.txt').write_text('''Code RED Faction War Pass12 Research Notes

Scope:
- More events in empty wilderness/roadless areas by strengthening placementglobals wilderness sets.
- More population pressure in wilderness regions through level.pop.
- A best-effort player-posse layer that uses low-density respawning ally/law defenders and a TR pulse that follows/helps the player when the engine exposes the player as an ally target.

Important limitation:
The staged content/tune archives did not expose direct Dutch/Javier/Bill actor templates. The pass therefore uses named companion-proxy pool names but stock safe templates. This avoids unknown actor/entity IDs that could fail to spawn.

Next deeper target:
- companion_brain.wsc, external task/squad objective files, and any actor template archives that contain named story characters.
''','utf-8')
    (ROOT/'README_INSTALL_AND_TEST_PASS12.txt').write_text('''CodeRedFactionWar Drop-In RPF Pass12 — Wilderness Living World + Player Posse Approximation

Use folder:
  DROP_IN_WILDERNESS_EVENTS_AND_PLAYER_POSSE

Install:
  1. Back up your current content.rpf and tune_d11generic.rpf.
  2. Copy this pass's content.rpf and tune_d11generic.rpf into the same place your test setup loads those files from.
  3. Test in wilderness first, then towns.

Best test areas:
  - Hennigan's Stead wilderness and trails
  - Cholla Springs empty areas
  - Gaptooth Ridge and Perdido
  - Diez Coronas / Diegos Bluff
  - Fort Mercer and Twin Rocks outskirts
  - Roads between Armadillo, Thieves Landing, and Hennigan's Ranch

Watch for:
  - More campfires, broken wagons, rebel/camp pressure, wild animal encounters, criminal chases, stickups, robberies, prisoner/wagon activity, and random wilderness trouble.
  - Law response and gang pressure appearing farther outside towns.
  - Low-density player-posse defenders. They are companion proxies because direct Dutch/Javier/Bill templates were not exposed in the staged content/tune archives.
  - If the engine treats the player as an ally target, posse proxies should try to follow/help/defend through the new TR pulse.
  - If they die, population pressure can spawn them again later; it is not a guaranteed instant respawn script.

Preserved:
  - Pass11 persistent camps/refgroups
  - Pass10 daily rival gang showdowns
  - Pass09 train robberies
  - Pass08 battle wagons/turret trucks
  - Pass06 Thieves Landing posse raids
  - No EXE/DLL/LIB/BAT/CMD/PS1/.red plugin binaries are included.

Honest limitation:
This pass does not add exact Dutch, Javier, or Bill models because those templates were not found in the current staged tune/content RPFs. It adds a safe stock-template ally posse layer first.
''','utf-8')
    forbidden={'.exe','.dll','.lib','.bat','.cmd','.ps1','.red'}
    for p in ROOT.rglob('*'):
        if p.is_file() and p.suffix.lower() in forbidden:
            raise RuntimeError(f'forbidden binary found: {p}')
    with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_STORED) as z:
        for p in ROOT.rglob('*'):
            if p.is_file():
                z.write(p,p.relative_to(ROOT.parent))
    print('BUILT', ZIP, ZIP.stat().st_size)
    print(json.dumps(validation,indent=2))

if __name__=='__main__':
    main()
