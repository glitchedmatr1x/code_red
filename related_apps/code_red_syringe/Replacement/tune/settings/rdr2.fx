sagProceduralFxManager
{
	CAMERASHAKE
	{
		FXName				"gunFireShake" 
		MinEulers			0.0	0.0	0.0
		MaxEulers	0.042700 0.000000 0.000000
		ShakeTime			0.244000
		DampeningShakeTime	0.110000
		MaxFovProportionDegrees	94.500000
	}
	
	CAMERASHAKE
	{
		FXName				"gunFireShakeTurret"
		MinEulers	-0.014000 0.000000 0.000000
		MaxEulers	0.015250 0.000000 0.000000
		ShakeTime			0.244000
		DampeningShakeTime	0.220000
		MaxFovProportionDegrees	94.500000
	}
	
	CAMERASHAKE
	{
		FXName				"cannonFireShakeCannon"
		MinEulers	-0.224000 -0.112000 0.000000
		MaxEulers	0.244000 0.122000 0.000000
		ShakeTime			0.610000
		DampeningShakeTime	0.550000
		MaxFovProportionDegrees	94.500000
	}
	
	CAMERASHAKE
	{
		FXName				"cannonFireShakeSniper"
		MinEulers	0.000000 -0.028000 0.000000
		MaxEulers	0.061000 0.030500 0.000000
		ShakeTime 0.244000
		DampeningShakeTime 0.220000
		MaxFovProportionDegrees	94.500000
	}
	CAMERASHAKE
	{
		FXName				"explosionShakeDynamite"
		MinEulers	0.000000 -0.028000 0.000000
		MaxEulers	0.061000 0.030500 0.000000
		ShakeTime 0.244000
		DampeningShakeTime 0.220000
		MaxFovProportionDegrees	94.500000
		Impulse	0.000000 9.450000 0.000000
		MaxYawAngle 0.664340
		SpringStrength 35.880000
		SpringDamping 0.324000
		ReshakeTime 0.276000
		MinTimeBetweenReshakes 0.032000
		MaxTimeBetweenReshakes 0.639600
		ReshakeIntensityBegin 0.561200
		ReshakeIntensityEnd 0.030680
		ShakeNearDistance 9.600000
		ShakeFarDistance 45.560000
		ShakeScaleAtFarDistance 0.020000
	}	
	CAMERASHAKE
	{
		FXName				"explosionShakeMolotov"
		MinEulers	0.000000 -0.028000 0.000000
		MaxEulers	0.061000 0.030500 0.000000
		ShakeTime 0.244000
		DampeningShakeTime 0.550000
		MaxFovProportionDegrees	94.500000
		Impulse	0.000000 1.350000 0.000000
		MaxYawAngle 0.546340
		SpringStrength 33.925000
		SpringDamping 0.216000
		ReshakeTime 0.120000
		MinTimeBetweenReshakes 0.120000
		MaxTimeBetweenReshakes 0.164000
		ReshakeIntensityBegin 0.744200
		ReshakeIntensityEnd 0.590000
		ShakeNearDistance 9.600000
		ShakeFarDistance 45.560000
		ShakeScaleAtFarDistance 0.062500
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
