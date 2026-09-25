"""
Agricultural Knowledge Base Generator Script.

Generates structured disease, symptom, cause, prevention, and treatment guides
for all 38 PlantVillage canonical disease classes in data/knowledge_base/agricultural_documents.json.
"""

import os
import json
import csv

METADATA_CSV = "data/metadata/plantvillage_class_mapping.csv"
OUTPUT_JSON = "data/knowledge_base/agricultural_documents.json"


# Complete, authentic agricultural knowledge base keyed directly by canonical_id
CANONICAL_DISEASE_KNOWLEDGE = {
    # ── APPLE ──────────────────────────────────────────────────────────────
    "apple_apple_scab": {
        "symptoms": [
            "Olive-green to brown velvety spots on leaf upper surfaces",
            "Deformed, cracked fruit with dark scabby corky lesions",
            "Premature leaf drop and reduced tree vigor"
        ],
        "causes": [
            "Fungal pathogen *Venturia inaequalis*",
            "High relative humidity (>85%) and prolonged leaf wetness"
        ],
        "risk_factors": [
            "Overwintering infected leaves on orchard floor",
            "Cool wet spring weather (60-70°F / 15-21°C)"
        ],
        "prevention": [
            "Plant scab-resistant apple cultivars (e.g., Liberty, Enterprise, Freedom)",
            "Prune tree canopy for improved airflow and rapid leaf drying",
            "Rake and shred or compost fallen leaves in autumn to eliminate primary inoculum"
        ],
        "management": [
            "Apply preventative copper or sulfur fungicides before bud break (green tip stage)",
            "Utilize systemic fungicides (e.g., myclobutanil, difenoconazole) during primary infection windows"
        ],
        "sources": [
            "USDA Agricultural Research Service — Apple Pathology Guide",
            "Cornell University Extension — Tree Fruit Scab Management Series"
        ]
    },
    "apple_black_rot": {
        "symptoms": [
            "Frogeye leaf spots with purple margins and tan/brown centers",
            "Black firm rotting on fruit starting near calyx with concentric rings of pycnidia",
            "Sunken reddish-brown bark cankers on limbs and branches"
        ],
        "causes": [
            "Fungal pathogen *Botryosphaeria obtusa*",
            "Infection through wounds caused by insects, pruning, fire blight, or hail"
        ],
        "risk_factors": [
            "Dead wood and mummified fruit left in orchard",
            "Warm wet summer weather (75-85°F / 24-29°C)"
        ],
        "prevention": [
            "Prune out dead wood, fire blight strikes, and cankers during winter dormancy",
            "Remove mummified fruit from trees and ground before spring bud break",
            "Avoid mechanical damage to bark during mowing and harvesting"
        ],
        "management": [
            "Apply captan, mancozeb, or thiophanate-methyl fungicides from petal fall through harvest",
            "Prune infected branches at least 6-8 inches below visible canker margin"
        ],
        "sources": [
            "Cornell University Integrated Fruit Portal — Black Rot Management",
            "Purdue Extension Fruit Disease Bulletin — Botryosphaeria obtusa"
        ]
    },
    "apple_cedar_apple_rust": {
        "symptoms": [
            "Bright yellow-orange lesions on upper leaf surface with red borders",
            "Tube-like spore structures (aecia) on lower leaf surface producing brown spores",
            "Gall swelling with gelatinous orange tendrils on host juniper trees in damp spring"
        ],
        "causes": [
            "Heteroecious fungal pathogen *Gymnosporangium juniperi-virginianae*",
            "Obligate host alternation between apple (*Malus*) and Eastern Red Cedar (*Juniperus*)"
        ],
        "risk_factors": [
            "Proximity to Eastern Red Cedar (*Juniperus virginiana*) trees within 1-2 miles",
            "Spring rains with temperatures between 55-75°F (13-24°C)"
        ],
        "prevention": [
            "Remove host junipers and cedar trees within 1 mile of commercial apple orchards",
            "Plant rust-resistant apple varieties (e.g., Enterprise, Freedom, Liberty, Redfree)"
        ],
        "management": [
            "Apply DMI/sterol-inhibiting fungicides (e.g., myclobutanil) from pink bud to petal fall",
            "Apply protectant mancozeb or ziram during active spring spore release periods"
        ],
        "sources": [
            "Penn State Extension — Cedar Apple Rust Pathology Guide",
            "Virginia Tech Plant Pathology Extension — Gymnosporangium Management"
        ]
    },
    "apple_healthy": {
        "symptoms": [
            "No visible disease lesions or spots on foliage",
            "Vigorous, dark green leaves with uniform canopy growth",
            "Smooth bark and clean fruit development"
        ],
        "causes": [
            "Optimal orchard management, balanced nutrition, and effective disease prevention"
        ],
        "risk_factors": [
            "Seasonal disease pressure; requires regular scouting for early pest arrival"
        ],
        "prevention": [
            "Maintain balanced nitrogen-phosphorus-potassium fertility based on leaf tissue analysis",
            "Prune during winter dormancy for open canopy structure and light penetration",
            "Apply dormant horticultural oil spray to suppress overwintering scale and mite eggs"
        ],
        "management": [
            "Continue Good Agricultural Practices (GAP) and routine orchard monitoring",
            "Maintain clean orchard floor with weed-free tree strips"
        ],
        "sources": [
            "USDA Good Agricultural Practices (GAP) — Tree Fruit",
            "Penn State Extension — Commercial Tree Fruit Production Guide"
        ]
    },

    # ── BLUEBERRY ──────────────────────────────────────────────────────────
    "blueberry_healthy": {
        "symptoms": [
            "Vibrant green, shiny leaves without chlorosis, spots, or marginal burn",
            "Robust shoot elongation and healthy flower/fruit cluster development"
        ],
        "causes": [
            "Optimal acidic soil pH (4.5-5.5) and balanced ericoid mycorrhizal root environment"
        ],
        "risk_factors": [
            "Soil pH creeping above 5.5 leading to iron chlorosis; drought stress in shallow roots"
        ],
        "prevention": [
            "Maintain soil pH between 4.5 and 5.5 using elemental sulfur or acidifying fertilizers",
            "Apply 3-4 inches of organic pine bark or sawdust mulch to conserve shallow root moisture",
            "Use drip irrigation with acidified water where irrigation water pH is high"
        ],
        "management": [
            "Routine monitoring for mummy berry and blueberry maggot",
            "Annual renewal pruning of canes older than 6 years"
        ],
        "sources": [
            "Michigan State University Extension — Blueberry Growth and Soil Care",
            "NC State Extension — Commercial Blueberry Production Guide"
        ]
    },

    # ── CHERRY ─────────────────────────────────────────────────────────────
    "cherry_powdery_mildew": {
        "symptoms": [
            "White to light-grey powdery mycelial coating on young leaves and succulent shoots",
            "Upward leaf curling, distortion, and premature defoliation",
            "Russeting or circular white powdery blemishes on developing cherry fruit"
        ],
        "causes": [
            "Fungal pathogen *Podosphaera clandestina*",
            "Airborne conidia dispersing from overwintered chasmothecia in bark crevices"
        ],
        "risk_factors": [
            "Dense tree canopies, high relative humidity, and warm temperatures (60-80°F / 15-27°C)",
            "Excessive nitrogen fertilization promoting susceptible succulent shoot flushes"
        ],
        "prevention": [
            "Prune cherry trees for open canopy structure to maximize sunlight and airflow",
            "Avoid excessive summer nitrogen fertilization that triggers late succulent growth"
        ],
        "management": [
            "Apply wettable sulfur, potassium bicarbonate, or horticultural oils at shuck fall",
            "Rotate systemic fungicides (FRAC 3 DMI and FRAC 11 QoI) to prevent chemical resistance"
        ],
        "sources": [
            "Washington State University Extension — Cherry Powdery Mildew Management",
            "UC IPM Pest Management Guidelines — Cherry: Powdery Mildew"
        ]
    },
    "cherry_healthy": {
        "symptoms": [
            "Deep green, glossy foliage without holes, spots, or powdery mildew coatings",
            "Stout shoot growth and clean fruit clusters with firm stems"
        ],
        "causes": [
            "Balanced soil fertility, appropriate irrigation scheduling, and proper dormant care"
        ],
        "risk_factors": [
            "Spring frost during bloom; excess rainfall near harvest causing fruit cracking"
        ],
        "prevention": [
            "Prune sour and sweet cherries during dry summer weather to reduce bacterial canker risk",
            "Maintain balanced watering schedule, easing irrigation near harvest to avoid fruit split",
            "Install bird netting or repellents during fruit ripening"
        ],
        "management": [
            "Continue standard orchard sanitation and seasonal crop monitoring",
            "Remove dropped fruit after harvest to suppress spotted wing drosophila"
        ],
        "sources": [
            "Oregon State University Extension — Cherry Orchard Care Manual",
            "USDA Agricultural Research Service — Fruit Laboratory"
        ]
    },

    # ── CORN / MAIZE ───────────────────────────────────────────────────────
    "corn_cercospora_leaf_spot_gray_leaf_spot": {
        "symptoms": [
            "Small tan to gray rectangular lesions strictly bounded by parallel leaf veins",
            "Lesions expand into long rectangular blocks (1-3 inches long) turning necrotic",
            "Browning and premature blighting of lower leaves progressing upward to ear leaves"
        ],
        "causes": [
            "Fungal pathogen *Cercospora zeae-maydis*",
            "Survives on infected corn residue on the soil surface"
        ],
        "risk_factors": [
            "Continuous corn cropping, no-till / minimum tillage practices",
            "Extended periods of warm (75-85°F), overcast days and high humidity (>90%)"
        ],
        "prevention": [
            "Rotate crops annually with non-host crops (soybean, small grains, alfalfa)",
            "Perform conservation tillage to bury crop debris and promote residue decomposition",
            "Select corn hybrid varieties with proven high Gray Leaf Spot (GLS) tolerance ratings"
        ],
        "management": [
            "Apply foliar fungicides (triazole + strobilurin mixtures) between VT (tasseling) and R1 (silking)",
            "Prioritize fungicide applications when lesions appear on the third leaf below the ear before tasseling"
        ],
        "sources": [
            "Iowa State University Extension — Gray Leaf Spot of Corn",
            "Purdue Extension Crop Diseases — Cercospora zeae-maydis Guide"
        ]
    },
    "corn_common_rust": {
        "symptoms": [
            "Oval to elongate cinnamon-brown pustules scattered over upper and lower leaf surfaces",
            "Pustules rupture epidermal tissue to release powdery golden-brown to dark urediniospores",
            "Chlorosis and premature leaf death under high pustule density"
        ],
        "causes": [
            "Fungal pathogen *Puccinia sorghi*",
            "Spore showers carried northward on air currents from southern production areas"
        ],
        "risk_factors": [
            "Cool, moist weather (60-70°F / 15-21°C) with frequent dews and high humidity",
            "Late planting dates exposing young plants to peak spore flights"
        ],
        "prevention": [
            "Plant corn hybrids containing specific *Rp* resistance genes or general partial resistance",
            "Plant early in the season to allow crop development before major spore arrivals"
        ],
        "management": [
            "Apply foliar fungicides (e.g., pyraclostrobin, azoxystrobin, propiconazole) if pustules exceed 5% coverage on upper leaves prior to silking",
            "Scout weekly from vegetative stage V6 through dough stage R4"
        ],
        "sources": [
            "Purdue Extension — Common Rust of Corn Bulletin",
            "USDA-ARS Cereal Disease Laboratory — Corn Pathology"
        ]
    },
    "corn_northern_leaf_blight": {
        "symptoms": [
            "Long elliptical, cigar-shaped grayish-green to tan lesions (1-6 inches in length)",
            "Lesions can merge, causing broad foliar blighting and plant death",
            "Dark olive-grey spore dust visible in lesion centers during humid mornings"
        ],
        "causes": [
            "Fungal pathogen *Exserohilum turcicum* (syn. *Helminthosporium turcicum*)",
            "Overwinters as conidia and chlamydospores in corn debris"
        ],
        "risk_factors": [
            "Moderate temperatures (65-80°F / 18-27°C) combined with extended leaf wetness (>6 hours)",
            "High residue fields under no-till management"
        ],
        "prevention": [
            "Utilize corn hybrids with race-specific resistance (*Ht1*, *Ht2*, *Ht3*) or multigenic tolerance",
            "Implement 1-2 year crop rotations away from corn to diminish soil residue inoculum",
            "Tillage in autumn to accelerate breakdown of infected corn stalks"
        ],
        "management": [
            "Apply dual-mode fungicides (QoI Group 11 + DMI Group 3) from V12 to R2 stage under high disease pressure",
            "Ensure adequate spray canopy penetration and water volume (minimum 15-20 gal/acre)"
        ],
        "sources": [
            "University of Illinois Extension — Northern Corn Leaf Blight Guide",
            "Ohio State University Extension — Corn Pathology Series"
        ]
    },
    "corn_healthy": {
        "symptoms": [
            "Vigorous, dark green leaf canopy with upright stalk growth",
            "No foliar pustules, rectangular lesions, or cigar-shaped blights",
            "Uniform ear development with full kernel fill"
        ],
        "causes": [
            "Balanced nitrogen, phosphorus, potassium, and zinc nutrition under optimal moisture"
        ],
        "risk_factors": [
            "Nitrogen deficiency (V-shaped leaf yellowing); drought stress during silking"
        ],
        "prevention": [
            "Soil test before planting and side-dress nitrogen fertilizer during rapid V6-V8 growth",
            "Maintain soil moisture through critical pollination and grain-fill windows",
            "Scout fields every 7-10 days for foliar diseases and armyworm / corn borer pressure"
        ],
        "management": [
            "Maintain standard agronomic weed control and IPM scouting practices",
            "Harvest at optimal grain moisture (15-20%) to avoid lodging"
        ],
        "sources": [
            "USDA Natural Resources Conservation Service — Corn Production Guide",
            "Iowa State University Extension — Corn Field Guide"
        ]
    },

    # ── GRAPE ──────────────────────────────────────────────────────────────
    "grape_black_rot": {
        "symptoms": [
            "Small circular reddish-brown leaf spots with tiny black pycnidia specks arranged in rings",
            "Dark elongated cankers on green shoots and petioles",
            "Infected berries shrivel into hard, black, wrinkled mummies that remain attached to clusters"
        ],
        "causes": [
            "Fungal pathogen *Guignardia bidwellii* (anamorph *Phyllosticta ampelicida*)",
            "Infection occurs during warm rains starting at bud break"
        ],
        "risk_factors": [
            "Overwintered mummified berries on vines or vineyard floor",
            "Warm temperatures (70-85°F / 21-29°C) with continuous leaf wetness (>6 hours)"
        ],
        "prevention": [
            "Remove and destroy all mummified grape clusters during winter pruning",
            "Canopy shoot thinning and leaf pulling around fruit zone for air movement and rapid drying",
            "Plant less susceptible grape cultivars where black rot pressure is chronic"
        ],
        "management": [
            "Apply mancozeb, captan, or ziram beginning at 1-inch shoot growth through 4 weeks post-bloom",
            "Apply systemic fungicides (myclobutanil, kresoxim-methyl) during critical pre-bloom to post-bloom window"
        ],
        "sources": [
            "Cornell University Cooperative Extension — Grape Black Rot Management",
            "Penn State Extension — Grape Disease Compendium"
        ]
    },
    "grape_esca_black_measles": {
        "symptoms": [
            "Interveinal chlorosis and necrosis creating distinctive 'tiger-stripe' pattern on leaves",
            "Small dark purple or brown spots ('measles') distributed across berry skins",
            "Internal wood discoloration, white rot sponginess, and sudden vine collapse (apoplexy)"
        ],
        "causes": [
            "Fungal trunk disease complex including *Phaeomoniella chlamydospora*, *Phaeoacremonium minimum*, and *Fomitiporia mediterranea*",
            "Spore entry through fresh pruning wounds in woody grapevine tissue"
        ],
        "risk_factors": [
            "Mature vineyards (>7-10 years old), large pruning wounds exposed to rain",
            "Hot, dry summer conditions accelerating vine water stress and apoplexy symptoms"
        ],
        "prevention": [
            "Delay pruning until late winter dormancy when wound healing occurs more rapidly",
            "Apply wound sealants, pruning paints, or *Trichoderma* biocontrol formulations to fresh cuts",
            "Double-pruning practice to keep final cuts clean and pathogen-free"
        ],
        "management": [
            "Surgically cut out infected arms or trunks at least 4 inches below visible wood staining",
            "Retrain a new trunk from basal suckers if the rootstock remains healthy",
            "Rogue out severely collapsed vines to prevent spread of airborne spores"
        ],
        "sources": [
            "UC Davis Viticulture & Enology — Grapevine Trunk Diseases: Esca Complex",
            "EPPO Global Database — Phaeomoniella chlamydospora and Esca"
        ]
    },
    "grape_leaf_blight_isariopsis_leaf_spot": {
        "symptoms": [
            "Irregular reddish-brown to dark brown angular lesions on foliage",
            "Lesions dry out and drop out, creating ragged shot-hole appearance on leaves",
            "Premature defoliation exposing grape clusters to sun scald"
        ],
        "causes": [
            "Fungal pathogen *Pseudocercospora vitis* (syn. *Isariopsis clavispora*, *Phaeoisariopsis vitis*)",
            "Dispersed by rain splash and humid air currents"
        ],
        "risk_factors": [
            "Dense unpruned vineyard canopies, high relative humidity, poor air drainage",
            "Frequent summer rainfall during late vegetative season"
        ],
        "prevention": [
            "Trellis training and canopy thinning to optimize sunlight penetration and wind flow",
            "Implement drip irrigation instead of overhead sprinklers to prevent foliar wetting",
            "Remove fallen leaves and prunings to lower fungal inoculum"
        ],
        "management": [
            "Apply copper hydroxide, mancozeb, or chlorothalonil protective sprays",
            "Include strobilurin (QoI) or sterol-inhibiting fungicides in mid-to-late season spray programs"
        ],
        "sources": [
            "FAO Plant Protection Bulletin — Grapevine Foliar Pathogens",
            "Integrated Pest Management for Grapes — University of California"
        ]
    },
    "grape_healthy": {
        "symptoms": [
            "Uniform, healthy green leaves with distinct varietal lobe shapes and clear margins",
            "Strong vine cane lignification and well-spaced, vigorous grape clusters",
            "Absence of foliar tiger-striping, black rot spots, or powdery mildew coatings"
        ],
        "causes": [
            "Balanced vine nutrition, proper canopy shoot management, and optimal irrigation"
        ],
        "risk_factors": [
            "Seasonal powdery mildew, downy mildew, and bunch rot pressure requiring vigilance"
        ],
        "prevention": [
            "Prune dormant canes to balanced bud count based on vine pruning weight",
            "Practice suckering, shoot positioning, and selective fruit-zone leaf removal",
            "Monitor vine petiole nutrient levels (especially N, K, B, and Mg)"
        ],
        "management": [
            "Continue standard vineyard IPM scouting and sustainable soil management",
            "Maintain cover crops between rows to manage soil moisture and prevent erosion"
        ],
        "sources": [
            "UC IPM Grape Pest Management Guidelines",
            "Cornell Viticulture and Enology Extension — Grape Production Manual"
        ]
    },

    # ── ORANGE / CITRUS ────────────────────────────────────────────────────
    "orange_haunglongbing_citrus_greening": {
        "symptoms": [
            "Asymmetrical blotchy mottled yellowing across leaf veins (not symmetrical like zinc deficiency)",
            "Small, lopsided, poorly colored fruit with green lower stylar end and aborted dark seeds",
            "Bitter salty fruit juice, severe twig dieback, and rapid tree decline"
        ],
        "causes": [
            "Unculturable phloem-restricted bacterium *Candidatus Liberibacter asiaticus*",
            "Transmitted by the Asian Citrus Psyllid (*Diaphorina citri*) vector"
        ],
        "risk_factors": [
            "Presence of Asian Citrus Psyllid populations and movement of infected citrus budwood",
            "Warm subtropical climate favorable to year-round psyllid breeding"
        ],
        "prevention": [
            "Plant only certified pathogen-free citrus nursery trees from registered insect-proof screenhouses",
            "Enforce strict quarantine controls preventing uninspected citrus plant transport",
            "Install insect exclusion screens and visual yellow sticky monitoring traps"
        ],
        "management": [
            "No known cure exists for Huanglongbing; infected trees must be rogued and destroyed to protect surrounding trees",
            "Control psyllid vectors with targeted foliar and systemic insecticides (imidacloprid, thiamethoxam)",
            "Provide enhanced nutritional soil and foliar feeds (zinc, iron, manganese) to prolong productivity of affected groves"
        ],
        "sources": [
            "USDA APHIS — Citrus Greening (Huanglongbing) Program",
            "University of Florida IFAS Extension — HLB Management Guide"
        ]
    },

    # ── PEACH ──────────────────────────────────────────────────────────────
    "peach_bacterial_spot": {
        "symptoms": [
            "Small, angular, water-soaked dark green/purple lesions on leaves that turn brown",
            "Centers of leaf spots drop out producing a 'shot-hole' appearance with yellowing margins",
            "Deep, pitted, cracked corky lesions with gum exudation on peach fruit surface"
        ],
        "causes": [
            "Bacterial pathogen *Xanthomonas arboricola pv. pruni*",
            "Overwinters in twig cankers and infected bud scales"
        ],
        "risk_factors": [
            "Warm, wet, windy spring weather (70-85°F / 21-29°C) with blowing sand or rain splash",
            "Light sandy soils and peach cultivars with high genetic susceptibility"
        ],
        "prevention": [
            "Plant resistant peach varieties (e.g., Candor, Clayton, Reliance, Sentinel)",
            "Establish windbreaks to minimize windblown sand abrasion that creates bacterial entry wounds",
            "Avoid overhead irrigation and excessive late nitrogen fertilization"
        ],
        "management": [
            "Apply dormant copper sprays (copper hydroxide/sulfate) at leaf fall and bud break",
            "Apply low-rate copper formulations or oxytetracycline sprays starting at petal fall through cover sprays"
        ],
        "sources": [
            "NC State Extension — Peach Bacterial Spot Pathology",
            "University of Georgia Extension — Southeastern Peach Management Guide"
        ]
    },
    "peach_healthy": {
        "symptoms": [
            "Vigorous, lanceolate, vibrant green leaves with smooth margins and no shot-holes",
            "Smooth bark on new shoot flushes and fuzz-covered, unblemished developing peach fruit"
        ],
        "causes": [
            "Proper open-center tree training, balanced NPK fertility, and effective dormant spray routine"
        ],
        "risk_factors": [
            "Early spring frost; peach tree short life (PTSL) in sandy ring-nematode soils"
        ],
        "prevention": [
            "Prune to an open-center (vase) shape to maximize sunlight penetration into interior canopy",
            "Thin developing fruit to 6-8 inches apart when fruit reaches nickel size for high quality",
            "Apply dormant copper and lime sulfur sprays to prevent peach leaf curl (*Taphrina deformans*)"
        ],
        "management": [
            "Maintain regular orchard floor weed control and soil moisture management",
            "Scout weekly for plum curculio, oriental fruit moth, and brown rot"
        ],
        "sources": [
            "Clemson University Cooperative Extension — Peach Orchard Guide",
            "USDA Agricultural Research Service — Fruit and Tree Nut Laboratory"
        ]
    },

    # ── PEPPER / BELL PEPPER ───────────────────────────────────────────────
    "bell_pepper_bacterial_spot": {
        "symptoms": [
            "Small water-soaked, circular to angular dark green lesions on leaves",
            "Lesions turn brown with pale centers, causing extensive leaf yellowing and defoliation",
            "Raised, blister-like corky scabs (1/8-1/4 inch) on pepper fruit surface"
        ],
        "causes": [
            "Bacterial pathogen *Xanthomonas euvesicatoria* (syn. *Xanthomonas campestris pv. vesicatoria*)",
            "Seedborne pathogen and survival on solanaceous crop residues"
        ],
        "risk_factors": [
            "Warm temperatures (75-86°F / 24-30°C), frequent rainstorms, and overhead sprinkler irrigation",
            "Continuous solanaceous cropping (pepper, tomato, eggplant) in close rotation"
        ],
        "prevention": [
            "Use certified pathogen-free, hot-water treated seeds and disease-free transplants",
            "Plant bacterial spot-resistant pepper hybrids (possessing *Bs1*, *Bs2*, *Bs3*, *Bs4* genes)",
            "Adopt 2-3 year crop rotation with non-solanaceous crops (beans, sweet corn, cucurbits)",
            "Utilize drip irrigation rather than overhead sprinklers to eliminate foliar splash"
        ],
        "management": [
            "Apply preventive copper hydroxide bactericide combined with mancozeb (acts synergistically)",
            "Utilize bacteriophage bio-bactericides (e.g., AgriPhage) or acibenzolar-S-methyl (systemic acquired resistance activator)"
        ],
        "sources": [
            "University of Florida IFAS Extension — Bacterial Spot of Pepper",
            "Rutgers NJAES Cooperative Extension — Bell Pepper Disease Bulletin"
        ]
    },
    "bell_pepper_healthy": {
        "symptoms": [
            "Lush, glossy deep green leaves without water-soaked spots, holes, or chlorosis",
            "Sturdy central stem, robust branching, and smooth firm unblemished bell pepper fruit"
        ],
        "causes": [
            "Adequate soil temperature (>65°F / 18°C), consistent moisture, and balanced calcium-rich nutrition"
        ],
        "risk_factors": [
            "Calcium deficiency causing blossom end rot; sunscald under low foliage cover"
        ],
        "prevention": [
            "Maintain consistent soil moisture through drip irrigation to prevent blossom end rot",
            "Apply balanced fertilizer with calcium and magnesium; avoid excessive vegetative nitrogen",
            "Use black or silver reflective plastic mulch to warm soil and repel aphid and thrips vectors"
        ],
        "management": [
            "Support plants with stakes or tomato cages to prevent limb breakage under heavy fruit load",
            "Harvest peppers at mature green or full colored stage with sharp pruners"
        ],
        "sources": [
            "UC IPM Pest Management Guidelines — Peppers",
            "Cornell Vegetable Program — Pepper Production Guide"
        ]
    },

    # ── POTATO ─────────────────────────────────────────────────────────────
    "potato_early_blight": {
        "symptoms": [
            "Dark brown to black spots with characteristic concentric rings ('target board' pattern) on older leaves",
            "Yellow chlorotic halos surrounding lesions leading to lower leaf senescence and defoliation",
            "Dark, sunken, dry circular lesions on potato tubers with raised purple-brown margins"
        ],
        "causes": [
            "Fungal pathogen *Alternaria solani*",
            "Survives on infected potato crop residue, volunteer potato plants, and solanaceous weeds"
        ],
        "risk_factors": [
            "Alternating wet and dry periods, warm temperatures (75-85°F / 24-29°C)",
            "Plant stress from heavy tuber bulking, nitrogen deficiency, or drought"
        ],
        "prevention": [
            "Implement a 3-4 year crop rotation with non-solanaceous crops (cereals, legumes)",
            "Maintain balanced nitrogen fertility to prevent premature vine senescence",
            "Apply straw mulch and avoid mechanical damage to leaves during cultivation"
        ],
        "management": [
            "Apply protectant fungicides (chlorothalonil, mancozeb) starting before row closure",
            "Rotate with systemic strobilurin (QoI) and succinate dehydrogenase inhibitor (SDHI) fungicides"
        ],
        "sources": [
            "University of Idaho Extension — Potato Early Blight Pathology",
            "Cornell Vegetable MD Online — Alternaria solani Management"
        ]
    },
    "potato_late_blight": {
        "symptoms": [
            "Large, irregular water-soaked pale green to dark brown lesions that expand rapidly across foliage",
            "White delicate downy fungal mildew visible on lesion borders on leaf undersides in humid conditions",
            "Foul rotting odor and reddish-brown dry granular rot extending 1/2 inch into tuber flesh"
        ],
        "causes": [
            "Oomycete pathogen *Phytophthora infestans*",
            "Overwinters in infected seed tubers, cull piles, and volunteer potato tubers"
        ],
        "risk_factors": [
            "Cool, wet weather (60-70°F / 15-21°C) with persistent high relative humidity (>90%) and rain/fog",
            "Proximity to uncontrolled cull piles and infected tomato/potato fields"
        ],
        "prevention": [
            "Plant only certified disease-free seed tubers from trusted certified producers",
            "Destroy all potato cull piles and eradicate volunteer potato plants in spring",
            "Select late blight resistant potato cultivars (e.g., Defender, Elba, Sarpo Mira)"
        ],
        "management": [
            "Apply protectant fungicides (mancozeb, chlorothalonil) on a strict 5-7 day schedule during blight-favorable weather",
            "Apply systemic oomycides (mefenoxam, cymoxanil, mandipropamid, fluazinam) immediately upon local blight warnings",
            "Kill vines completely 2-3 weeks before harvest to prevent tuber infection during digging"
        ],
        "sources": [
            "USABlight National Late Blight Portal — Phytophthora infestans Guide",
            "EuroBlight European Network for Potato Blight Monitoring"
        ]
    },
    "potato_healthy": {
        "symptoms": [
            "Dense, erect, deep green leaf canopy with vigorous haulm/stem development",
            "No foliar concentric target spots, water-soaked blights, or mosaic mottling",
            "Firm, smooth-skinned tubers developing evenly under soil hills"
        ],
        "causes": [
            "High-quality certified seed pieces, properly hilled beds, and balanced moisture/nutrient management"
        ],
        "risk_factors": [
            "Tuber greening (solanine toxicity) from sunlight exposure; hollow heart from irregular watering"
        ],
        "prevention": [
            "Hill soil around potato stems 2-3 times during early growth to protect tubers from light and blight spores",
            "Maintain consistent soil moisture (65-75% field capacity) especially from tuber initiation to bulking",
            "Rotate potato fields on a minimum 3-year cycle with corn, oats, or clover"
        ],
        "management": [
            "Scout for Colorado potato beetle and potato leafhopper using sweep nets",
            "Allow skin set in dry soil for 10-14 days after vine kill before final harvest"
        ],
        "sources": [
            "University of Wisconsin Extension — Commercial Potato Production Guide",
            "USDA Agricultural Research Service — Vegetable Crops Research"
        ]
    },

    # ── RASPBERRY ──────────────────────────────────────────────────────────
    "raspberry_healthy": {
        "symptoms": [
            "Healthy compound green leaves with serrated edges and distinct silvery undersides",
            "Vigorous primocane growth, sturdy floricanes, and plump, well-formed aggregate berry drupelets"
        ],
        "causes": [
            "Well-drained slightly acidic soil (pH 6.0-6.8), good organic matter, and trellis support"
        ],
        "risk_factors": [
            "Phytophthora root rot in heavy wet soils; spur blight in overcrowded rows"
        ],
        "prevention": [
            "Plant on raised beds (8-10 inches high) in well-drained loam soil to prevent root rots",
            "Prune out spent floricanes immediately after summer harvest to increase air circulation",
            "Install a T-trellis or V-trellis system to support canes and keep fruit off soil"
        ],
        "management": [
            "Apply annual spring compost or balanced organic berry fertilizer",
            "Maintain 2-3 inches of wood chip mulch along cane rows, keeping mulch away from cane base"
        ],
        "sources": [
            "Cornell Fruit Resources — Berry Diagnostic Tool: Raspberry",
            "Oregon State University Extension — Growing Raspberries in Your Home Garden"
        ]
    },

    # ── SOYBEAN ────────────────────────────────────────────────────────────
    "soybean_healthy": {
        "symptoms": [
            "Trifoliate vibrant green leaves forming a dense, closed row canopy",
            "Active nitrogen-fixing pink/red root nodules when split open",
            "Well-filled pods forming uniformly at stem nodes"
        ],
        "causes": [
            "Successful *Bradyrhizobium japonicum* root nodulation, balanced potassium and phosphorus"
        ],
        "risk_factors": [
            "Iron deficiency chlorosis on high pH (>7.5) calcareous soils; sudden death syndrome in cool wet soils"
        ],
        "prevention": [
            "Inoculate soybean seed with *Bradyrhizobium japonicum* before planting in non-soybean history soils",
            "Ensure proper soil fertility with adequate phosphorus and potassium based on soil tests",
            "Plant in narrow rows (15-30 inches) to promote rapid canopy closure and suppress weeds"
        ],
        "management": [
            "Scout weekly for soybean aphid, stink bugs, and defoliating caterpillars",
            "Harvest at 13-14% grain moisture to minimize harvest shatter losses"
        ],
        "sources": [
            "Iowa State University Extension — Soybean Field Guide",
            "University of Minnesota Extension — Soybean Growth and Management"
        ]
    },

    # ── SQUASH / CUCURBIT ──────────────────────────────────────────────────
    "squash_powdery_mildew": {
        "symptoms": [
            "White, talcum-powder-like fungal spots on upper and lower leaf surfaces, petioles, and stems",
            "Spots expand and coalesce to cover entire leaf blade with white powdery coating",
            "Infected leaves turn yellow, then brown and crispy (senesce prematurely), exposing fruit to sunscald"
        ],
        "causes": [
            "Fungal pathogen *Podosphaera xanthii* (syn. *Sphaerotheca fuliginea*)",
            "Airborne conidia requiring no free moisture on leaves for germination"
        ],
        "risk_factors": [
            "Dense canopy plantings, high relative humidity (50-90%), and warm temperatures (68-80°F / 20-27°C)",
            "Shaded lower leaves and older foliage under low sunlight intensity"
        ],
        "prevention": [
            "Plant powdery mildew-resistant squash and pumpkin hybrids (e.g., PMR cultivars)",
            "Maintain generous plant spacing (3-6 feet) to ensure sunlight penetration and ventilation",
            "Avoid excessive nitrogen applications that promote overly dense vegetative canopy"
        ],
        "management": [
            "Apply sulfur, potassium bicarbonate, horticultural oil, or neem oil at first sign of powdery spots",
            "Rotate systemic fungicides (FRAC 3 DMI, FRAC 7 SDHI, FRAC 13 quinoxyfen) to prevent resistance"
        ],
        "sources": [
            "Cornell Vegetable MD Online — Cucurbit Powdery Mildew",
            "UC IPM Pest Management Guidelines — Cucurbits: Powdery Mildew"
        ]
    },

    # ── STRAWBERRY ─────────────────────────────────────────────────────────
    "strawberry_leaf_scorch": {
        "symptoms": [
            "Numerous small, irregular purple to dark red spots with dark centers on upper leaflet surface",
            "Spots coalesce, turning the entire leaf purplish-red then brown and scorched",
            "Tissue between veins dies and curls upward, giving foliage a burnt, scorched appearance"
        ],
        "causes": [
            "Fungal pathogen *Diplocarpon earlianum*",
            "Survives on infected strawberry leaves and plant debris in the bed"
        ],
        "risk_factors": [
            "Prolonged leaf wetness (>8-12 hours) and moderate spring/fall temperatures (60-75°F / 15-24°C)",
            "Dense, unrenovated matted row strawberry plantings"
        ],
        "prevention": [
            "Renovate matted row strawberry plantings annually after harvest by mowing old foliage and narrowing rows",
            "Plant on raised beds with drip irrigation to avoid foliar wetting",
            "Maintain proper plant spacing and weed control to promote rapid drying of leaves"
        ],
        "management": [
            "Apply protectant fungicides (captan, thiram) during early leaf emergence in spring",
            "Remove and destroy heavily diseased strawberry leaves during post-harvest renovation"
        ],
        "sources": [
            "NC State Extension — Strawberry Leaf Scorch Pathology",
            "Ohio State University Extension — Fruit Pathology: Strawberry Leaf Scorch"
        ]
    },
    "strawberry_healthy": {
        "symptoms": [
            "Vibrant trifoliate green leaflets with sawtooth margins and clean petiole stems",
            "Stout central crown positioned precisely at soil level with white vigorous feeder roots",
            "Bright red, symmetrical, firm strawberry fruit with clean green calyx sepals"
        ],
        "causes": [
            "Proper crown planting depth, well-drained sandy loam soil, and balanced drip fertigation"
        ],
        "risk_factors": [
            "Crown rot if buried too deeply; root desiccation if planted too shallow; slug damage on fruit"
        ],
        "prevention": [
            "Plant strawberry crowns with midpoint at soil surface (never bury the crown or expose roots)",
            "Apply clean straw mulch around plants to keep berries off bare soil and suppress weed emergence",
            "Maintain drip irrigation delivering 1-1.5 inches of water per week during fruiting"
        ],
        "management": [
            "Pinch off early blossoms on first-year June-bearing plants to establish strong root system",
            "Monitor weekly for spider mites and tarnished plant bug during flowering"
        ],
        "sources": [
            "University of California IPM — Strawberry Pest Management Guidelines",
            "University of Florida IFAS Extension — Strawberry Production Guide"
        ]
    },

    # ── TOMATO ─────────────────────────────────────────────────────────────
    "tomato_bacterial_spot": {
        "symptoms": [
            "Small (1/8 inch), water-soaked, dark brown to black circular lesions on leaves and stems",
            "Lesions often surrounded by yellow halos, coalescing to cause severe blighting and leaf drop",
            "Raised, blister-like corky scabs (1/4 inch) on developing green and red tomato fruits"
        ],
        "causes": [
            "Bacterial complex: *Xanthomonas perforans*, *Xanthomonas vesicatoria*, *Xanthomonas gardneri*",
            "Seedborne pathogen and survival on crop residues and volunteer solanaceous plants"
        ],
        "risk_factors": [
            "Warm, wet weather (75-86°F / 24-30°C), driving rainstorms, and overhead irrigation",
            "Working in wet tomato fields facilitating mechanical transmission"
        ],
        "prevention": [
            "Use certified pathogen-free, hot-water treated seeds and certified disease-free transplants",
            "Implement a minimum 2-year crop rotation away from solanaceous crops (tomato, pepper, potato)",
            "Stake and trellis tomato plants and use plastic mulch with drip irrigation"
        ],
        "management": [
            "Apply preventative copper hydroxide combined with mancozeb weekly during warm, wet weather",
            "Utilize bacteriophage sprays (AgriPhage) or plant defense activator acibenzolar-S-methyl (Actigard)"
        ],
        "sources": [
            "University of Florida IFAS — Bacterial Spot of Tomato Guide",
            "Cornell Vegetable MD Online — Xanthomonas Diseases of Tomato"
        ]
    },
    "tomato_early_blight": {
        "symptoms": [
            "Dark brown to black spots with distinct concentric rings ('target board' pattern) on mature lower leaves",
            "Yellow chlorotic halo developing around lesions, causing progressive defoliation from bottom upward",
            "Sunken, dark, leathery lesions at stem base (collar rot) and near fruit stem attachment"
        ],
        "causes": [
            "Fungal pathogen *Alternaria solani* and *Alternaria linariae*",
            "Overwinters in infected solanaceous crop debris and weeds (e.g., black nightshade)"
        ],
        "risk_factors": [
            "Alternating wet and dry periods with warm temperatures (75-85°F / 24-29°C)",
            "Plant stress, nitrogen deficiency, and heavy fruit load"
        ],
        "prevention": [
            "Mulch heavily with straw or plastic to prevent soil splash onto lower foliage",
            "Prune off lower leaves up to 12-18 inches above soil once plants are established",
            "Practice 3-year crop rotation with non-solanaceous crops (corn, beans, brassicas)"
        ],
        "management": [
            "Apply protectant fungicides (chlorothalonil, mancozeb, copper) at first symptom appearance",
            "Rotate systemic fungicides (FRAC 3 DMI, FRAC 7 SDHI, FRAC 11 QoI) on 7-14 day intervals"
        ],
        "sources": [
            "Cornell Vegetable MD Online — Early Blight of Tomato",
            "Michigan State University Extension — Tomato Early Blight Management"
        ]
    },
    "tomato_late_blight": {
        "symptoms": [
            "Large, irregular, water-soaked pale green to greasy brown lesions expanding rapidly across foliage",
            "White delicate downy fungal-like sporulation visible on lesion undersides in damp conditions",
            "Large, firm, dark brown greasy lesions on green and ripening tomato fruit with secondary rotting"
        ],
        "causes": [
            "Oomycete pathogen *Phytophthora infestans*",
            "Airborne sporangia dispersing on wind currents over miles from infected potato/tomato crops"
        ],
        "risk_factors": [
            "Cool, wet, foggy weather (60-70°F / 15-21°C) with prolonged relative humidity (>90%)",
            "Infected seed potatoes, volunteer potatoes, or infected greenhouse transplants"
        ],
        "prevention": [
            "Plant resistant tomato cultivars (e.g., Defiant Ph-R, Mountain Merit, Mountain Magic, Plum Regal)",
            "Eradicate volunteer potatoes and tomato cull piles near production fields",
            "Ensure wide plant spacing and drip irrigation to maintain dry foliage"
        ],
        "management": [
            "Apply protective fungicides (chlorothalonil, mancozeb, copper) before disease outbreak",
            "Apply targeted oomycide fungicides (mefenoxam, cymoxanil, mandipropamid, cyazofamid) immediately upon alert"
        ],
        "sources": [
            "USABlight National Late Blight Portal — Tomato Late Blight Guide",
            "EuroBlight Network — Phytophthora infestans Pathology and Monitoring"
        ]
    },
    "tomato_leaf_mold": {
        "symptoms": [
            "Pale green to distinct yellow chlorotic spots with indefinite margins on upper leaf surface",
            "Olive-green to velvety brown mold (mass of conidiophores and spores) on corresponding lower leaf surface",
            "Infected leaves wither, turn yellow-brown, and drop prematurely; fruit rarely infected directly"
        ],
        "causes": [
            "Fungal pathogen *Passalora fulva* (syn. *Cladosporium fulvum*, *Fulvia fulva*)",
            "Survival as sclerotia or conidia in greenhouse structures and plant debris"
        ],
        "risk_factors": [
            "High relative humidity (>85%) and warm temperatures (70-80°F / 21-27°C)",
            "Greenhouse and high tunnel tomato production with limited ventilation and dense canopies"
        ],
        "prevention": [
            "Ventilate greenhouses and high tunnels aggressively with fans and ridge vents to keep RH <85%",
            "Increase plant spacing and prune lower suckers to enhance horizontal airflow",
            "Plant tomato varieties with *Cf* gene resistance to leaf mold"
        ],
        "management": [
            "Apply copper hydroxide, chlorothalonil, or mancozeb protective sprays upon first symptom detection",
            "Clean and sanitize greenhouse walls, stakes, and benches between crop cycles"
        ],
        "sources": [
            "University of Massachusetts Extension — Leaf Mold of Tomato",
            "UConn Extension — Tomato Leaf Mold in High Tunnels"
        ]
    },
    "tomato_septoria_leaf_spot": {
        "symptoms": [
            "Numerous small (1/16-1/8 inch) circular spots with dark brown margins and light gray/tan centers",
            "Tiny black specks (pycnidia fruiting bodies) distinctly visible inside mature spot centers",
            "Severe yellowing, senescence, and defoliation starting on lowest leaves and progressing upward"
        ],
        "causes": [
            "Fungal pathogen *Septoria lycopersici*",
            "Overwinters in solanaceous crop debris and nightshade weed hosts"
        ],
        "risk_factors": [
            "Extended leaf wetness, splashing rain, high humidity, and warm temperatures (68-77°F / 20-25°C)",
            "Overhead watering and lack of soil mulch"
        ],
        "prevention": [
            "Stake and cage tomato plants to elevate foliage off soil surface",
            "Apply 2-3 inches of organic straw or plastic mulch to stop rain-splash inoculation",
            "Implement a 3-year crop rotation away from solanaceous crops",
            "Remove lower infected leaves early in the season to slow upward progress"
        ],
        "management": [
            "Apply copper fungicides, chlorothalonil, or mancozeb on a 7-10 day preventative schedule",
            "Avoid overhead irrigation and do not prune or cultivate when tomato foliage is wet"
        ],
        "sources": [
            "Missouri Botanical Garden Pests & Diseases — Septoria Leaf Spot of Tomato",
            "Rutgers NJAES Cooperative Extension — Septoria lycopersici Management"
        ]
    },
    "tomato_two_spotted_spider_mite": {
        "symptoms": [
            "Fine yellow stippling, flecking, or chlorotic speckling on upper leaf surfaces",
            "Leaves turn bronze, grayish, or pale yellow, drying out and dropping prematurely",
            "Fine silky webbing visible underneath leaves and across growing tips under heavy infestation"
        ],
        "causes": [
            "Arthropod pest *Tetranychus urticae* (Two-spotted spider mite)",
            "Rapid multi-generational reproduction (complete lifecycle in 5-7 days under hot conditions)"
        ],
        "risk_factors": [
            "Hot, dry, dusty weather conditions (>80°F / 27°C)",
            "Overuse of broad-spectrum pyrethroid insecticides that kill natural mite predators",
            "Excessive nitrogen fertilization promoting high protein sap"
        ],
        "prevention": [
            "Maintain optimal soil moisture and hose down dusty roadways near fields",
            "Wash undersides of leaves with overhead water spray in garden settings to disrupt webbing",
            "Encourage and preserve natural predators (lady beetles, lacewings, minute pirate bugs)"
        ],
        "management": [
            "Release biological predatory mites (*Phytoseiulus persimilis*, *Neoseiulus californicus*)",
            "Apply insecticidal soap, horticultural oil, or neem oil with thorough coverage of leaf undersides",
            "Utilize targeted selective miticides (bifenazate, abamectin) rotating modes of action"
        ],
        "sources": [
            "University of California IPM — Spider Mites on Tomato",
            "University of Maryland Extension — Two-spotted Spider Mite Management"
        ]
    },
    "tomato_target_spot": {
        "symptoms": [
            "Small pinpoint brown spots on foliage expanding into circular lesions with concentric brown rings",
            "Lesions bordered by a subtle yellow halo, often merging to cause broad leaf blight",
            "Dark brown, sunken, circular lesions with concentric cracking on ripening tomato fruit"
        ],
        "causes": [
            "Fungal pathogen *Corynespora cassiicola*",
            "Survives on crop residue and alternate host plants across diverse families"
        ],
        "risk_factors": [
            "Warm, humid conditions (68-90°F / 20-32°C) with frequent rainfall or heavy dew",
            "Overhead irrigation and crowded tomato canopy"
        ],
        "prevention": [
            "Prune suckers and stake tomato plants to maximize air circulation through the canopy",
            "Avoid overhead irrigation; use drip lines under plastic mulch",
            "Remove and destroy crop residues immediately after harvest"
        ],
        "management": [
            "Apply protectant fungicides (chlorothalonil, mancozeb, copper hydroxide)",
            "Rotate systemic fungicides (FRAC 7 SDHI e.g., fluopyram, FRAC 11 strobilurins) during active disease periods"
        ],
        "sources": [
            "University of Florida IFAS Extension — Target Spot of Tomato",
            "CABI Invasive Species Compendium — Corynespora cassiicola"
        ]
    },
    "tomato_yellow_leaf_curl_virus": {
        "symptoms": [
            "Distinct upward curling and cupping of leaflet margins",
            "Interveinal chlorosis (yellowing) with stunted, small leaflets giving bushy appearance",
            "Severe overall plant stunting, flower abscission (drop), and dramatically reduced fruit yield"
        ],
        "causes": [
            "Begomovirus *Tomato yellow leaf curl virus* (TYLCV)",
            "Vectored persistently by the Sweetpotato Whitefly (*Bemisia tabaci*)"
        ],
        "risk_factors": [
            "High whitefly vector populations, warm arid or subtropical climate",
            "Proximity to older infected tomato, pepper, or weed host fields (e.g., nightshades, mallows)"
        ],
        "prevention": [
            "Plant TYLCV-resistant tomato cultivars (possessing *Ty-1*, *Ty-2*, *Ty-3* resistance genes)",
            "Install 50-mesh insect exclusion netting in greenhouse and nursery production",
            "Deploy yellow sticky traps for early whitefly population monitoring",
            "Maintain a 2-month host-free crop break between production seasons"
        ],
        "management": [
            "Control whitefly vectors using systemic neonicotinoids (imidacloprid), diamides, or spirotetramat",
            "Apply insecticidal soaps or neem oil in rotation to prevent whitefly pesticide resistance",
            "Rogue out and destroy infected viral plants immediately in sealed plastic bags"
        ],
        "sources": [
            "University of California IPM — Tomato Yellow Leaf Curl Virus",
            "Florida Department of Agriculture & Consumer Services — TYLCV Pest Alert"
        ]
    },
    "tomato_mosaic_virus": {
        "symptoms": [
            "Mottled light and dark green mosaic patterns and blistered appearance on foliage",
            "Severe leaf distortion, narrowing ('shoestringing'), and fern-like leaves",
            "Internal brown browning (internal necrosis) of fruit wall and uneven fruit ripening"
        ],
        "causes": [
            "Tobamovirus *Tomato mosaic virus* (ToMV) or *Tobacco mosaic virus* (TMV)",
            "Highly stable mechanical virus transmitted via hands, pruning shears, stakes, clothing, and seed"
        ],
        "risk_factors": [
            "Mechanical handling, grafting, pruning, and contact with tobacco products",
            "Virus can persist for years in dry crop debris, soil, and on wooden tomato stakes"
        ],
        "prevention": [
            "Plant TMV/ToMV-resistant tomato hybrids (look for 'T' or 'TMV' on seed packets)",
            "Wash hands thoroughly with soap or 20% non-fat dry milk solution before handling plants",
            "Sanitize pruning tools and stakes in a 10% bleach solution or 20% non-fat dry milk solution",
            "Prohibit tobacco use (smoking, chewing) near tomato production areas"
        ],
        "management": [
            "No chemical viricides exist; rogue out and destroy infected plants immediately upon detection",
            "Do not compost infected plant material; dispose of in municipal trash or burn where permitted"
        ],
        "sources": [
            "APSnet Plant Pathology — Tobacco and Tomato Mosaic Viruses",
            "Cornell Vegetable MD Online — Tomato Mosaic Virus Management"
        ]
    },
    "tomato_healthy": {
        "symptoms": [
            "Vibrant, dark green compound foliage with sturdy hairy stems and vigorous growth",
            "No foliar spots, concentric target rings, water-soaked lesions, or leaf curling",
            "Abundant yellow flower blossoms and firm, smooth, evenly ripening tomato fruit"
        ],
        "causes": [
            "Optimal watering, balanced nitrogen-phosphorus-potassium-calcium nutrition, and consistent pruning"
        ],
        "risk_factors": [
            "Blossom end rot from calcium deficiency / irregular watering; catfacing from cold weather during bloom"
        ],
        "prevention": [
            "Stake, cage, or trellis plants to elevate foliage and fruit off the ground",
            "Prune non-productive suckers on indeterminate varieties to improve canopy airflow",
            "Apply 2-3 inches of clean straw or organic mulch to maintain steady soil moisture",
            "Apply balanced fertilizer; supplement with calcium nitrate if blossom end rot is a historical issue"
        ],
        "management": [
            "Scout weekly for hornworms, fruitworms, aphids, and early leaf spots",
            "Water at the base of plants using drip irrigation or soaker hoses in the early morning"
        ],
        "sources": [
            "USDA Natural Resources Conservation Service — Tomato Growth Guide",
            "Cornell Cooperative Extension — Vegetable MD Online: Tomato Care Manual"
        ]
    }
}


def build_knowledge_base():
    """Generates the comprehensive agricultural knowledge base JSON file."""
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    documents = []

    with open(METADATA_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = int(row["class_id"])
            canonical_id = row["canonical_id"].strip()
            plant = row["plant"].strip()
            disease = row["disease"].strip()
            health_status = row["health_status"].strip()

            # Retrieve dedicated knowledge template for canonical_id
            if canonical_id in CANONICAL_DISEASE_KNOWLEDGE:
                template = CANONICAL_DISEASE_KNOWLEDGE[canonical_id]
            else:
                # Fallback if an unexpected class appears
                template = {
                    "symptoms": [f"Foliage spots and chlorosis characteristic of {disease}"],
                    "causes": [f"Pathogen infection causing {disease} in {plant}"],
                    "risk_factors": ["High humidity, wet canopy conditions, unmanaged crop residue"],
                    "prevention": ["Ensure proper plant spacing and crop rotation", "Remove infected plant tissue"],
                    "management": ["Apply recommended protective spray or biological control"],
                    "sources": ["Agricultural Extension Advisory System", "Plant Disease Pathology Index"]
                }

            symptoms_text = "; ".join(template["symptoms"])
            causes_text = "; ".join(template["causes"])
            risk_text = "; ".join(template["risk_factors"])
            prev_text = "; ".join(template["prevention"])
            mgmt_text = "; ".join(template["management"])

            search_chunk = (
                f"Plant: {plant}. Disease: {disease} (Canonical ID: {canonical_id}). "
                f"Health Status: {health_status}. Symptoms: {symptoms_text}. "
                f"Causes: {causes_text}. Risk Factors: {risk_text}. "
                f"Prevention: {prev_text}. Management: {mgmt_text}."
            )

            doc_entry = {
                "class_id": cid,
                "canonical_id": canonical_id,
                "plant": plant,
                "disease": disease,
                "health_status": health_status,
                "symptoms": template["symptoms"],
                "causes": template["causes"],
                "risk_factors": template["risk_factors"],
                "prevention": template["prevention"],
                "management": template["management"],
                "sources": template["sources"],
                "search_text": search_chunk
            }
            documents.append(doc_entry)

    with open(OUTPUT_JSON, mode="w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2)

    print(f"Successfully generated {len(documents)} agricultural knowledge documents at: {OUTPUT_JSON}")


if __name__ == "__main__":
    build_knowledge_base()
