#condition:
#soil_moisture <0.2 & rain_probability < 0.6: water
#soil_moisture > 0.3: don't water
#forecast_rain_mm > 5 & rain_probability > 0.6: don't water
def recommend_watering(soil_moisture, forecast_rain_mm, rain_probability):
    if soil_moisture is None: 
        return "insufficient soil moisture data"
    if forecast_rain_mm is None:
        return "insufficient forecast rain data"
    if rain_probability is None:
        return "insufficient rain probability data"
    if soil_moisture >= 0.3:
        return "don't water"
    else: #soil_moisture <0.3:
        if forecast_rain_mm >= 5 or rain_probability >= 0.6:
            return "don't water"
        else:
            return "water"