# Caveman â€” Before/After Examples

## Lite Mode Examples

### Example 1: Code Review Response
**Before (Normal verbose):**
Certainly! I would be more than happy to help you with that. Looking closely at your authentication middleware, it appears to me that there might be a subtle issue with how the JWT token expiration is validated. You might want to consider checking whether the token is null before calling the verify method. Here is the updated code snippet that you can use...

**After (/caveman lite):**
In your auth middleware, JWT expiration check lacks a null check before verification. Here is the fix:

Ê—¬r¸©´)¥˜€ …Ñ½­•¸¤Ñ¡É½Ü¹•ÜÕÑ¡ÉÉ½È ‰5¥ÍÍ¥¹œÑ½­•¸ˆ¤ì)Ö§t¹Ù•É¥™ä¡Ñ½­•¸°Í•É•Ð¤ì(((´´´((ŒŒÕ±°5½‘”á…µÁ±•Ì((ŒŒŒá…µÁ±”€ÈèQ•ÍÐ…¥±ÕÉ”¥…¹½Í¥Ì(¨©	•™½É”€¡9½Éµ…°Ù•É‰½Í”¤è¨¨)$É…¸Ñ¡”Ñ•ÍÐÍÕ¥Ñ”™½Èå½Ô…¹Õ¹™½ÉÑÕ¹…Ñ•±ä€È½ÕÐ½˜Ñ¡”€ÄÔÑ•ÍÑÌ™…¥±•¸%ÐÍ••µÌÑ¡…ÐÑ¡”‘…Ñ…‰…Í”½¹¹•Ñ¥½¸Ñ¥µ•½ÕÐ‘ÕÉ¥¹œÑ¡”¥¹Ñ•É…Ñ¥½¸Ñ•ÍÐ•á•ÕÑ¥½¸¸Q¡¥Ì¥Ì±¥­•±ä¡…ÁÁ•¹¥¹œ‰•…ÕÍ”Ñ¡”±½…°A½ÍÑÉ•ME0‘½­•È½¹Ñ…¥¹•ÈÝ…Ì¹½ÐÍÑ…ÉÑ•ÁÉ¥½ÈÑ¼ÉÕ¹¹¥¹œÑ¡”Ñ•ÍÐÉÕ¹¹•È¸]½Õ±å½Ô±¥­”µ”Ñ¼ÍÑ…ÉÐÑ¡”½¹Ñ…¥¹•È™½Èå½Ôü((¨©™Ñ•È€ ½…Ù•µ…¸™Õ±°¤è¨¨)I…¸Ñ•ÍÑÌ¸€È™…¥±•°€ÄÌÁ…ÍÍ•¸(´I½½Ð…ÕÍ”è½¹¹•Ñ¥½¸Ñ¥µ•½ÕÐ¥¸¥¹Ñ•É…Ñ¥½¸Ñ•ÍÑÌ¸(´…ÕÍ”èA½ÍÑÉ•ME0‘½­•È½¹Ñ…¥¹•ÈÍÑ½ÁÁ•¸(´Ñ¥½¸¹••‘•èIÕ¸‘½­•È½µÁ½Í”ÕÀ€µÁ½ÍÑÉ•Í€¸((´´´((ŒŒU±ÑÉ„5½‘”á…µÁ±•Ì((ŒŒŒá…µÁ±”€Ìè	Õ¥±€˜Y•É¥™¥…Ñ¥½¸MÑ…ÑÕÌ(¨©	•™½É”€¡9½Éµ…°Ù•É‰½Í”¤è¨¨)$¡…Ù”½µÁ±•Ñ•‰Õ¥±‘¥¹œÑ¡”QåÁ•MÉ¥ÁÐÁÉ½©•ÐÕÍ¥¹œÑÍ‘½Ý¸¸Ù•ÉåÑ¡¥¹œ½µÁ¥±•±•…¹±äÝ¥Ñ é•É¼•ÉÉ½ÉÌ…¹•¹•É…Ñ•Ñ¡”½ÕÑÁÕÐ¥¸Ñ¡”‘¥ÍÐ‘¥É•Ñ½Éä¸±°€ÐàÙ¥Ñ•ÍÐÑ•ÍÑÌÁ…ÍÍ•ÍÕ•ÍÍ™Õ±±ä¥¸€Ì¸ÐÍ•½¹‘Ì¸((¨©™Ñ•È€ ½…Ù•µ…¸Õ±ÑÉ„¤è¨¨)	Õ¥±è=,€¡‘¥ÍÐ½€¤)Q•ÍÑÌè€Ðà¼ÐàAML€ Ì¸ÑÌ¤)Y•É‘¥ÐèAML(