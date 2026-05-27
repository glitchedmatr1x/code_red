sagProceduralFxManager
{
	CAMERASHAKE
	{
		FXName				"gunFireShake" 
		MinEulers			0.0	0.0	0.0
		MaxEulers			0.035 0.0	0.0
		ShakeTime			0.2
		DampeningShakeTime	0.1
		MaxFovProportionDegrees	90.0
	}
	
	CAMERASHAKE
	{
		FXName				"gunFireShakeTurret"
		MinEulers			-0.01250	0.0	0.0
		MaxEulers			0.01250 0.0	0.0
		ShakeTime			0.2
		DampeningShakeTime	0.2
		MaxFovProportionDegrees	90.0
	}
	
	CAMERASHAKE
	{
		FXName				"cannonFireShakeCannon"
		MinEulers			-0.20 -0.10	0.0
		MaxEulers			0.200 0.10	0.0
		ShakeTime			0.5
		DampeningShakeTime	0.5
		MaxFovProportionDegrees	90.0
	}
	
	CAMERASHAKE
	{
		FXName				"cannonFireShakeSniper"
		MinEulers 0.0 -0.025 0.0
		MaxEulers 0.050 0.025 0.0
		ShakeTime 0.2
		DampeningShakeTime 0.2
		MaxFovProportionDegrees	90.0
	}
	CAMERASHAKE
	{
		FXName				"explosionShakeDynamite"
		MinEulers 0.0 -0.025 0.0
		MaxEulers 0.050 0.025 0.0
		ShakeTime 0.2
		DampeningShakeTime 0.2
		MaxFovProportionDegrees	90.0
		Impulse 0.0 7.0 0.0
		MaxYawAngle 0.563
		SpringStrength 31.2
		SpringDamping 0.3
		ReshakeTime 0.23
		MinTimeBetweenReshakes 0.04
		MaxTimeBetweenReshakes 0.78
		ReshakeIntensityBegin 0.46
		ReshakeIntensityEnd 0.026
		ShakeNearDistance 8.0
		ShakeFarDistance 34.0
		ShakeScaleAtFarDistance 0.01
	}	
	CAMERASHAKE
	{
		FXName				"explosionShakeMolotov"
		MinEulers 0.0 -0.025 0.0
		MaxEulers 0.050 0.025 0.0
		ShakeTime 0.2
		DampeningShakeTime 0.5
		MaxFovProportionDegrees	90.0
		Impulse 0.0 1.0 0.0
		MaxYawAngle 0.463
		SpringStrength 29.5
		SpringDamping 0.2
		ReshakeTime 0.0
		MinTimeBetweenReshakes 0.15
		MaxTimeBetweenReshakes 0.2
		ReshakeIntensityBegin 0.61
		ReshakeIntensityEnd 0.5
		ShakeNearDistance 8.0
		ShakeFarDistance 34.0
		ShakeScaleAtFarDistance 0.05
	}
	
	HUD_BLIP
	{ 
		FXName		"ENM_SHOOT_BLIP_RED"
		Duration			2.0
		IconIndex			0
		EnemyOnly			1
	}

	RMPTFX
	{
		FXName		"MUZZLE_LAMP"
		RMPTFXName	"amb_lantern_lit_always"
	}

	RMPTFX
	{
		FXName		"WEAP_LAMP_TRAIL"
		RMPTFXName	"weap_kerosine_trail"
	}

	RMPTFX
	{
		FXName		"MUZZLE_DYNAMITE"
		RMPTFXName	"muzzle_dynamite"
	}

	RMPTFX
	{
		FXName		"WEAP_DYNAMITE_TRAIL"
		RMPTFXName	"weap_dynamite_trail"
	}

	RMPTFX
	{
		FXName		"MUZZLE_FIREBOTTLE"
		RMPTFXName	"muzzle_fire_bottle"
	}

	RMPTFX
	{
		FXName		"WEAP_FIREBOTTLE_TRAIL"
		RMPTFXName	"weap_fire_bottle_trail"
	}

	RMPTFX
	{
		FXName		"MUZZLE_SMOKE"
		RMPTFXName	"muzzle_pistol"
	}

	RMPTFX
	{
		FXName		"MUZZLE_FLASH1"
		RMPTFXName	"muzzle_pistol_smoke"
	}

	RMPTFX
	{
		FXName		"MUZZLE_FLASH2"
		RMPTFXName	"muzzle_rifle_smoke"
	}

	RMPTFX
	{
		FXName		"MUZZLE_FLASH3"
		RMPTFXName	"muzzle_shotgun_smoke"
	}

	RMPTFX
	{
		FXName		"MUZZLE_CANNON"
		RMPTFXName	"muzzle_cannon"
	}

	RMPTFX
	{
		FXName		"WEAP_CANNON_TRAIL"
		RMPTFXName	"weap_cannon_trail"
	}

	RMPTFX
	{
		FXName		"MUZZLE_SHOTGUN"
		RMPTFXName	"muzzle_shotgun_smoke"
	}

	RMPTFX
	{
		FXName		"MUZZLE_GATLING"
		RMPTFXName	"muzzle_gatling"
	}

	RMPTFX
	{
		FXName		"EMIT_FLIES_01"
		RMPTFXName	"amb_flies"
	}

	RMPTFX
	{
		FXName		"MOLOTOV_MINI_FIRE"
		RMPTFXName	"exp_fire_bottle"
	}

	RMPTFX
	{
		FXName		"CAVE_TREMOR"
		RMPTFXName	"amb_cave_tremor"
	}

	
	DECALFX
	{
		FXName		"DECAL_MOLOTOV_SCORCH"
		DECALType	"EXPLOSION"
		DECALSize	1.5
	}
	
	BULLETTRAIL
	{
		FXName		"BULLET_TRAIL"
		BulletTrailFXName		"weap_bullet_trail"
	}
	
	RMPTFX
	{
		FXName		"THROWN_ThrowingKnife"
		RMPTFXName	"weap_knife_trail"
	}
	
	DECALFX
	{
		FXName		"DECAL_BIG_SCORCH"
		DECALType	"EXPLOSION"
		DECALSize	3.5
	}
	
	EXPLOSIONFX
	{
		FXName		"MOLOTOV_EXPLODE_DYN"
		RMPTFX		"MOLOTOV_MINI_FIRE"
		DECALFX		"DECAL_MOLOTOV_SCORCH"
		NumProbes	5
		RandomScale	.35
	}

	EXPLOSIONFX
	{
		FXName		"BIG_EXPLODE_DYN"
		RMPTFX		"MOLOTOV_MINI_FIRE"
		DECALFX		"DECAL_BIG_SCORCH"
		NumProbes	8
		RandomScale	.55
	}

	DECALFX
	{
		FXName		"DECAL_BULLET_HIT"
		DECALType	"BULLET"
		DECALSize	.02
	}
	
	RMPTFX
	{
		FXName		"DYNAMITE_EXPLODE"
		RMPTFXName	""
	}
	
	RMPTFX
	{
		FXName		"DYNAMITE_CRATEEXP"
		RMPTFXName	"exp_dynamite_wood"
	}
	
	RMPTFX
	{
		FXName		"FIREBOTTLE_EXPLODE"
		RMPTFXName	""
	}

	RMPTFX
	{
		FXName		"CANNON_EXPLOSION"
		RMPTFXName	""
	}
	
	DECALFX
	{
		FXName		"DECAL_CANNON_HIT"
		DECALType	"CANNON"
		DECALSize	0.3
	}

	RMPTFX
	{
		FXName		"KEROSENELAMP_EXPLODE"
		RMPTFXName	"exp_lantern"
	}

	RMPTFX
	{
		FXName		"TNT_WAGON_EXPLODE"
		RMPTFXName	"Script_exp_transport_TNT"
	}

	RMPTFX
	{
		FXName		"DYNAMITE_GRND"
		RMPTFXName	"exp_dynamite_buried"
	}
	
	RMPTFX
	{
		FXName		"DYNAMITE_MERCHANT03"
		RMPTFXName	"script_exp_transport_TNT"
	}
	
	RMPTFX
	{
		FXName		"TRAIN_BOILER_EXPLODE"
		RMPTFXName	""
	}
}
