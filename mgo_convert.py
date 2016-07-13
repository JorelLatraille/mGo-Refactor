# attribute name conversion for mGo supported shaders
# reverse == False, going from Application to Mari
# reverse == True, going from Mari to Application

print "mgo_convert v.1"

def VRayMtl(attr_data, reverse=False):
    converted_data = []
    data = {}
    cd = {}   # conversion dictionary
    cd["color"] = 'DiffuseColor'
    cd["diffuseColorAmount"] = 'DiffuseAmount'
    cd["opacityMap"] = 'Opacity_Map'
    cd["roughnessAmount"] = 'DiffuseRoughness'
    cd["illumColor"] = 'Self_Illumination'
    cd["brdfType"] = 'BRDF_Model'
    cd["reflectionColor"] = 'ReflectionColor'
    cd["reflectionColorAmount"] = 'ReflectionAmount'
    cd["hilightGlossinessLock"] = 'Lock_Highlight_Refle_gloss'
    cd["hilightGlossiness"] = 'HighlightGlossiness'
    cd["reflectionGlossiness"] = 'ReflectionGlossiness'
    cd["useFresnel"] = 'Fresnel_On'
    cd["lockFresnelIORToRefractionIOR"] = 'Fresnel_useIOR'
    cd["fresnelIOR"] = 'Reflection_IOR'
    cd["ggxTailFalloff"] = 'ggxTailFalloff'
    cd["anisotropy"] = 'Anisotropy'
    cd["anisotropyRotation"] = 'Rotation'
    cd["refractionColor"] = 'RefractionColor'
    cd["refractionColorAmount"] = 'RefractionAmount'
    cd["refractionGlossiness"] = 'RefractionGlossiness'
    cd["refractionIOR"] = 'IOR'
    cd["fogColor"] = 'Fog_Color'
    cd["fogMult"] = 'Fog_multiplier'
    cd["fogBias"] = 'Fog_bias'
    cd["sssOn"] = 'SSS_On'
    cd["translucencyColor"] = 'Translucency_Color'
    cd["scatterDir"] = 'Fwd_back_coeff'
    cd["scatterCoeff"] = 'Scatt_coeff'

    if reverse:
        print "reversing!"
        cd = dict((y, x) for x, y in cd.iteritems())

    for key, value in attr_data.iteritems():
        print key, value

        # convert old attribute key names to Mari defined attribute names
        for old_key, new_key in cd.iteritems():
            if key == old_key:
                key = new_key

                data[key] = value

                converted_data.append([key, value])
    return data
