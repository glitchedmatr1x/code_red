# Code RED Camp Car Workbench Report

Root: `C:\Users\glitc\OneDrive\Desktop\CodeRED_RPF_Extracts`
Candidates: `300`

Boundary: read-only. No archives, game files, or extracted files modified.

## Verdict

Code RED can read enough from the extracted workspace to drive this lane internally. The current evidence favors a two-path plan: keep the compiled `camp_car_probe.xsc` as the runtime proof, while using gringo/script/reference scans to identify one safe host or descriptor for a future copied-archive import proof.

## Recommended next move

1. Keep using `camp_car_probe.xsc` for runtime spawn proof.
2. Do not replace player camp scripts directly.
3. Use the top `playercamp` and vehicle script leads only to identify host behavior.
4. Look for XML/WSI/WGD host references before any copied-archive import proof.

## playercamp_hosts — 5

- score `89` — `content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc`
  - tags: playercamp, wsi
- score `41` — `content/release64/scripting/gringo/commonscripts/playercamp02_gringo.wsc`
  - tags: playercamp
- score `41` — `content/release64/scripting/gringo/commonscripts/playercamp03_gringo.wsc`
  - tags: playercamp
- score `41` — `content/release64/scripting/gringo/commonscripts/playercamp04_gringo.wsc`
  - tags: playercamp
- score `41` — `content/release64/scripting/gringo/commonscripts/playercampfootlocker.wsc`
  - tags: playercamp

## vehicle_script_leads — 5

- score `66` — `content/release64/scripting/gringo/commonscripts/vehicle_generator.wsc`
  - tags: vehicle_generator
- score `59` — `content/release64/scripting/gringo/commonscripts/car_gringo.wsc`
  - tags: car_gringo
- score `59` — `content/release64/scripting/gringo/commonscripts/playercar.wsc`
  - tags: playercar
- score `59` — `content/release64/scripting/gringo/commonscripts/traincar_gringo.wsc`
  - tags: car_gringo
- score `37` — `content/release64/scripting/gringo/gringobrains/gringobrainscripts/gen_vehicle_brain.wsc`
  - tags: vehicle_brain

## descriptor_hosts — 40

- score `99` — `content/dlc/zombiepack/gringos/dlc_rand_idle_sit_ground_player.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\Rand_Idle_Sit_Ground_Player` query: `AttachProp` radius: `10.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_bonnie_sit_rifle.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `75.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_cannibal_man.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again1.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again1b.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2a.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `UseAnim` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2b.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SpawnPoint` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2c.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_eating_dynamic.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_escalera_fema_sit_crying.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_female_cower.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SpawnPoint` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_fenway2a.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `UseAnim` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_fenway2b.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SpawnPoint` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_fenway4_others.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SpawnPoint` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_fenway4_rifle.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_landon_sitting.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_mckenna1.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `75.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_merchant_2_a.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_merchant_2_b.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_mexico_crossing1.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`

## placement_dictionary_leads — 13

- score `89` — `content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc`
  - tags: playercamp, wsi
- score `55` — `content/ui/boot.sc.xml`
  - tags: dlc_or_zombie, wsi
- score `55` — `content/ui/pausemenu/netstats/main.sc.xml`
  - tags: dlc_or_zombie, wsi
- score `47` — `content/ui/pausemenu/net/offlinemenu.sc.xml`
  - tags: wsi
- score `35` — `content/release64/dlc/zombiepack/beats/beat_trapped_survivor.sco`
  - tags: dlc_or_zombie, wsi
- score `35` — `content/release64/dlc/zombiepack/frontier/gaptooth_ridge/gaptooth_breach/gaptoothbreach_z.sco`
  - tags: dlc_or_zombie, wsi
- score `35` — `content/release64/dlc/zombiepack/rcm/mackenna/rcm_mackenna1.sco`
  - tags: dlc_or_zombie, wgd
- score `35` — `content/release64/dlc/zombiepack/rcm/return/rcm_return2.wsc`
  - tags: dlc_or_zombie, wgd
- score `35` — `content/release64/dlc/zombiepack/system/short_update_thread_z.sco`
  - tags: dlc_or_zombie, wsi
- score `35` — `content/release64/frontier/cholla_springs/coots_chapel/cootschapel.wsc`
  - tags: wgd
- score `35` — `content/release64/frontier/missions/ranch03/ranch03.wsc`
  - tags: wsi
- score `35` — `content/release64/mexico/missions/mexarmy02/mexarmy02.wsc`
  - tags: wsi
- score `35` — `content/release64/north/missions/home01/home01.wsc`
  - tags: wsi

## dlc_zombie_examples — 40

- score `99` — `content/dlc/zombiepack/gringos/dlc_rand_idle_sit_ground_player.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\Rand_Idle_Sit_Ground_Player` query: `AttachProp` radius: `10.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_bonnie_sit_rifle.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `75.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_cannibal_man.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again1.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again1b.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2a.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `UseAnim` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2b.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SpawnPoint` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2c.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_eating_dynamic.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_escalera_fema_sit_crying.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_female_cower.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SpawnPoint` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_fenway2a.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `UseAnim` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_fenway2b.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SpawnPoint` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_fenway4_others.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SpawnPoint` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_fenway4_rifle.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_landon_sitting.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `AttachProp` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_mckenna1.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `75.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_merchant_2_a.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_merchant_2_b.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`
- score `89` — `content/dlc/zombiepack/gringos/dlc_mexico_crossing1.xml`
  - tags: descriptor, dlc_or_zombie
  - refs: content\scripting\gringo\CommonScripts
  - script: `content\scripting\gringo\CommonScripts\GenericGringo` query: `SingleHotspot` radius: `0.0`

## Top candidates

### score 99 — `content/dlc/zombiepack/gringos/dlc_rand_idle_sit_ground_player.xml`
- suffix: `.xml` size: `5359` sha1_head: `F03B312AE56969B87D984A4E91ACD64FA22D6BD0`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\Rand_Idle_Sit_Ground_Player`
- ActivationRadius: `10.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\Rand_Idle_Sit_Ground_Player</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">PlayerUse</mp_Que
- `camp`: 0"/>  				</Item>  				<Item type="ggoItemStringAttrib">  					<mp_AttribName content="ascii">UseName</mp_AttribName>  					<mp_StringValue content="ascii">sit_camp</mp_StringValue>  				</Item>  				<Item type="ggoItemFloatAttrib">  					<mp_AttribName content="ascii">StartingPhaseTimeout</mp_AttribName>  					<fFloatValu
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\Rand_Idle_Sit_Ground_Pl

### score 89 — `content/dlc/zombiepack/gringos/dlc_bonnie_sit_rifle.xml`
- suffix: `.xml` size: `5946` sha1_head: `D4DE58323CD74D8F2A0A1E5A21941EC24B8FC4FF`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `75.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_cannibal_man.xml`
- suffix: `.xml` size: `6890` sha1_head: `80F450C183E14B0B75041B31CB7EA090C0807FD9`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_dead_rise_again1.xml`
- suffix: `.xml` size: `5799` sha1_head: `02DD71B1109FFCE589914DB53805A37E0066CF75`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_dead_rise_again1b.xml`
- suffix: `.xml` size: `6433` sha1_head: `3DD1027AC21842CCCDEAD2D8FAAE0C14E829D57C`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">Human</mp_QueryName>  			<Attri
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">Human</mp_

### score 89 — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2a.xml`
- suffix: `.xml` size: `9053` sha1_head: `67C2E782F52495CBF455A15D5FE00ADE370968E1`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `UseAnim`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2b.xml`
- suffix: `.xml` size: `4785` sha1_head: `9A83023990986B8E70DCF8DE1F0729F55CCD31CD`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpawnPoint`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_dead_rise_again2c.xml`
- suffix: `.xml` size: `6744` sha1_head: `705398203219EC11461FB8C62847AA0F22DCA50C`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_eating_dynamic.xml`
- suffix: `.xml` size: `5054` sha1_head: `F7DBF96485C7FF37E40616374E576926E8A17834`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_escalera_fema_sit_crying.xml`
- suffix: `.xml` size: `5092` sha1_head: `7D7FACB982CF6BF3D6CA6F9F9BCB847307B004DE`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_female_cower.xml`
- suffix: `.xml` size: `4763` sha1_head: `4E00D3207E19B143F91B3FC1959B54C5FA415B32`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpawnPoint`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_fenway2a.xml`
- suffix: `.xml` size: `8994` sha1_head: `932E6FFC7219F24DF595487509EB6B6F83B8A824`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `UseAnim`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_fenway2b.xml`
- suffix: `.xml` size: `4758` sha1_head: `E6D8E6137FFB89CAB3A7BBFEFA41FE9F78DB150E`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpawnPoint`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_fenway4_others.xml`
- suffix: `.xml` size: `4750` sha1_head: `A72E54986E777943F56ED9F3D709EED65F3BE762`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpawnPoint`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_fenway4_rifle.xml`
- suffix: `.xml` size: `5765` sha1_head: `E72BAAD268AF450D267DBE47197E56D678DFD693`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_landon_sitting.xml`
- suffix: `.xml` size: `5776` sha1_head: `61CFC02D9CC91165EC1BBF7B0F3D9E8EC88B92AF`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mckenna1.xml`
- suffix: `.xml` size: `4899` sha1_head: `3D5250AF6262EA5F6FB506EB3074E1C53A672371`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `75.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_merchant_2_a.xml`
- suffix: `.xml` size: `5067` sha1_head: `1CD8FDDBC5A7D76DB1C45F418658C58315BAFCB8`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_merchant_2_b.xml`
- suffix: `.xml` size: `5062` sha1_head: `6B0FC323D35462045DE8DAE27FAFEEDB34CF33E9`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mexico_crossing1.xml`
- suffix: `.xml` size: `5049` sha1_head: `D91A366CD7CB7032F8E0E2B65DB4F6F763BB47D9`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mexico_crossing2.xml`
- suffix: `.xml` size: `5049` sha1_head: `268AAD3CA9C5231506CAF2F70DB138C2106C43E2`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mexico_crossing3.xml`
- suffix: `.xml` size: `5049` sha1_head: `373AC456B201C157D6BCB4096B7E178EDDEFDC74`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mexico_crossing_b1.xml`
- suffix: `.xml` size: `5074` sha1_head: `142669C3A7CA393F53A276FFB25C435CBDF08411`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mexico_crossing_b2.xml`
- suffix: `.xml` size: `5071` sha1_head: `40A708E64696FF48BF111768FDB6A2BBD4E5F9B9`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mexico_crossing_z1.xml`
- suffix: `.xml` size: `4785` sha1_head: `4E54802A3C668F7260A205EFDA904E45EDD26E83`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpawnPoint`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mexico_crossing_z2.xml`
- suffix: `.xml` size: `4785` sha1_head: `77E600A7D7676B8EFF2E9F360424F32D69FAE398`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpawnPoint`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mother_superior_waiting.xml`
- suffix: `.xml` size: `5772` sha1_head: `9471E26AE1F3D2B23B9BE7A4F584D9E6BE953D64`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mourn_dead_body.xml`
- suffix: `.xml` size: `9905` sha1_head: `B318508B348118A6977BA437AFE000A00CD8ADC4`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpeechConts`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mourn_suicide.xml`
- suffix: `.xml` size: `9893` sha1_head: `7493C6CB815655F9F78E7B4F1E91346D541B723D`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpeechConts`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_mourn_suicide_original.xml`
- suffix: `.xml` size: `5754` sha1_head: `51AFE5DE1927F427B573D28707406AE5A61F9451`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_nun_bencha.xml`
- suffix: `.xml` size: `5029` sha1_head: `4D558F685A18B31D07F398B45F92771E31A64325`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_nun_benchb.xml`
- suffix: `.xml` size: `5029` sha1_head: `6558AF2A7EF28F7E4BE931FAD7ED26F21AEF0829`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_nun_benchc.xml`
- suffix: `.xml` size: `5029` sha1_head: `C6CFFBA89A5087C15AC75C271F93A05A62749D00`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_outbreak3.xml`
- suffix: `.xml` size: `4750` sha1_head: `EB36778F19759F8823C4EE6BE60E7C71612C257F`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpawnPoint`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_rcm_mother_superior.xml`
- suffix: `.xml` size: `9332` sha1_head: `B1930E49BA9E55DD3F2A70E769A4EDFF906AF46F`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpeechConts`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_robber_struggle.xml`
- suffix: `.xml` size: `9894` sha1_head: `4D1E7D17E74EDEA84770472F82DCF13FE5879798`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpeechConts`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_sasquatch2.xml`
- suffix: `.xml` size: `4754` sha1_head: `A4EDA823DF73A80DEC66B7991223FF4D9F43025C`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpawnPoint`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_stand_kneelvomit_n_any.xml`
- suffix: `.xml` size: `3848` sha1_head: `777F137CF5583A2E59ACAC1B19362051EEFF1D89`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_survivor_fight.xml`
- suffix: `.xml` size: `5046` sha1_head: `31EFBBB70F50E52E10F0C3794AB8E475120BB113`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_survivor_kneel_rfl.xml`
- suffix: `.xml` size: `5037` sha1_head: `B85C0FD14241090DCB6F7C5A877399FE7A68C128`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_survivor_low_wall_rfl.xml`
- suffix: `.xml` size: `5046` sha1_head: `8D6B4367104F367CD81EE63A4CD202459042F856`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_survivor_roof_rfl.xml`
- suffix: `.xml` size: `5034` sha1_head: `D687C6587B304C434124354BC1A160B4CB9A0328`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_survivor_stand_rfl.xml`
- suffix: `.xml` size: `5037` sha1_head: `E15F9756F7D7F6A0FA15080F5B40D6A4425D551A`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_survivor_window_rfl.xml`
- suffix: `.xml` size: `5040` sha1_head: `90F15F1E5774C624636155B8A13E326B37DDB524`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/dlc_unforgiven.xml`
- suffix: `.xml` size: `9868` sha1_head: `C1BCB637A0D1CBBA719FAE0BC4D4B297D567024D`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpeechConts`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/treasure_hunter_handoff_z.xml`
- suffix: `.xml` size: `9979` sha1_head: `83E5D74E74EC8964A85667B33A4BBAA66F651766`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `UseAnim`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_family_overrun.xml`
- suffix: `.xml` size: `9927` sha1_head: `8964388CB726A5A8752FC5F0F8D8259D5A5C5E5C`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpeechConts`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_z_beat_door.xml`
- suffix: `.xml` size: `5043` sha1_head: `68885F25C78F4CD26A16706B176759A627B4BDDB`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_z_climb.xml`
- suffix: `.xml` size: `5031` sha1_head: `6E20C7E8B3842C90ACA016ECF014C6118A44F0DB`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_z_family.xml`
- suffix: `.xml` size: `10888` sha1_head: `E672D8A1AE4EDF46F83E0727E321B222ECCB79E7`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `AttachProp`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_z_overrun_attack1.xml`
- suffix: `.xml` size: `9893` sha1_head: `187CA432043AD49519B6B064CAF732E0FB2D3358`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpeechConts`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_z_overrun_attack2.xml`
- suffix: `.xml` size: `9892` sha1_head: `C87987CFB54E70784DAB13B1E7718E2512E72B8A`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SpeechConts`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_z_overrun_attacked.xml`
- suffix: `.xml` size: `5034` sha1_head: `7D89113C3A2C8D62B3CD2F9C05E98CD901BA743C`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_z_overrun_dropgun.xml`
- suffix: `.xml` size: `5033` sha1_head: `EBD3D745BB890796B53E5FF4D2225A95CC08E26C`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/z_dlc_z_overrun_suicide.xml`
- suffix: `.xml` size: `5033` sha1_head: `90ACDAE0716DE4FDD12342DF29698867DEF69441`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/zombiepack_getmissingposter.xml`
- suffix: `.xml` size: `5848` sha1_head: `75D4A6DD1077EFE9CF1C6EF4655DE4E8E7C78D3B`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `PoleAnimation`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GetWantedPosterGround`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GetWantedPosterGround</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">PlayerUse</mp_QueryName
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GetWantedPosterGround</
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GetWantedPosterGround</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">Pl

### score 89 — `content/dlc/zombiepack/gringos/zombiepack_horsehitch.xml`
- suffix: `.xml` size: `5246` sha1_head: `682624D2C462B2D3D1F491D7C8B1364D354370A2`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\horseHitching`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\horseHitching</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\horseHitching</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\horseHitching</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/zombiepack_horsehitch2.xml`
- suffix: `.xml` size: `5245` sha1_head: `C359F985828480AB33AF9E490060151A73CD9653`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `SingleHotspot`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\horseHitching`
- ActivationRadius: `0.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\horseHitching</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\horseHitching</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\horseHitching</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/dlc/zombiepack/gringos/zombiepack_placeposter.xml`
- suffix: `.xml` size: `6381` sha1_head: `B8C45B61A9C22440F924CF90B27FC85370F3989F`
- tags: descriptor, dlc_or_zombie
- mp_QueryName: `PoleAnimation`
- mp_ScriptName: `content\scripting\gringo\CommonScripts\GenericGringo`
- ActivationRadius: `1.0`
- `content\scripting\gringo\CommonScripts`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</mp_QueryName>  			<At
- `gringo`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_Scrip
- `scripting`: <?xml version="1.0" encoding="UTF-8"?>  <ggoItemGringo>  	<mp_QueryName content="ascii">SimpleUseGringo</mp_QueryName>  	<mp_ScriptName content="ascii">content\scripting\gringo\CommonScripts\GenericGringo</mp_ScriptName>  	<GringoComponentList>  		<Item type="ggoComponentUseContext">  			<mp_QueryName content="ascii">UseCase1</

### score 89 — `content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc`
- suffix: `.wsc` size: `10562` sha1_head: `877A581D5FDB9AC163E621ECC1C4277C738A6E3D`
- tags: playercamp, wsi
- `wsi`:  xxnt +iT_ <"s8 vmrk p-YL CiTRB Y2]{@U;z Vj~LIE "7)v ^h7\ 6KB:Y .:1n nPd> CB,pzBY (E"z cYta P["P eZ='f w?:V ]vhf 2:po !xn# LU@6 ,ipMI&v h"//{ "JvE9 |hR( IH*( XoWsIu o`7* D%FG qAg- v.^} |{}XD D*@lSb )WpOe CLG~#mHA Xs'b d p|Y Sj~@; j6q<U F)7` >49_r PUX} igJj Kes\h *xWI X-W7 {<gqn us&@ =vNR 0"/- lO/H 6=lp{;w ('pO 3*GE (^MD [
