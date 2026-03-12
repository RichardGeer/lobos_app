Overview
Objective
Lobos is a meal-generation product for GLP-1 users.
It must:
Authenticate users via WordPress


Confirm paid membership status


Create and maintain a Lobos-specific user profile


Allow meal generation using structured inputs


Apply GLP-1 stage logic to influence recipe selection


Persist user data and meal history

System Architecture

Backend Functionality: All users have a dedicated account with a history. User recipes and meal history are saved in their account. As long as they are a customer, they can access this information.


WordPress Responsibilities
WordPress will provide via API:
Field
Type
first_name
string
email
string
membership_status
boolean (paid / not paid)


User ID
Unique identifier






Lobos Responsibilities
Lobos must:
Authenticate user via email


Validate membership_status == paid (then user can access)


Block access if membership_status == false


Create Lobos user profile on first login


Store all product-related data internally

On Login (background):
Lobos receives (from Wordpress):


first_name


email


membership_status


System checks:


If membership_status == false → show:
 “Active membership required to access Lobos.”
 (No product access.)


If membership_status == true:


If user does not exist → create new Lobos user record


If user exists → load existing profile


Email is the unique identifier.

PREFERENCES (editable)
If new user, fill this out (preferences)…
Field
Type
Required
current_weight
number
yes
goal_weight
number
yes
height
string
yes
birthYear
integer
yes
allergies
multi-select
yes
eating_style
single select
yes
glp1_status
single select
yes
(possibly)
glp1_dosage
Single select
yes



PREFERENCES FIELD DETAILS

Required Fields
First name
Last name
Current weight <<DARREN - is it better to do ranges as a drop down or make free form?>>
Goal weight
Height
Age

Allergies (required multi check) 
No allergies (Y/N)


Gluten_free (Y/N)


dairy_free (Y/N)


soy_free (Y/N)


egg_free (Y/N)


nut_free (Y/N)


Other Allergy (free form) 
Eating Style (single select) 
No Preference – default
Keto – Low-carb, high-fat approach that suppresses appetite via ketosis
Paleo – Whole-food, ancestral eating pattern with moderate carbs and protein
Mediterranean – Balanced intake of fats, fiber, and lean proteins with a heart-healthy focus
Green Mediterranean – Plant-forward Mediterranean with added polyphenols and minimal meat
Whole Food Plant-Based (WFPB) – 100% plant-based, high-fiber, minimally processed nutrition
Vegetarian – Plant-based with inclusion of dairy and/or eggs, no meat or fish
Flexitarian – Mostly plant-based with occasional inclusion of animal protein
Pegan – Hybrid of Paleo and Vegan principles, low-grain, anti-inflammatory
Whole30 – 30-day elimination protocol removing sugar, grains, dairy, and legumes
Vegan – 100% plant-based; excludes all animal products including dairy, eggs, and honey
Low-FODMAP - definition limits poorly absorbed carbohydrates that can trigger bloating, gas, pain, and diarrhea, especially in people with IBS.

<<DARREN UI DIRECTION - The next fields only show up if the user selects ADVANCED INPUTS>>

UPON OPENING LOBOS (after user has filled in the Preferences section)

User sees 
Darren, ideally, the user can edit any of these fields, and then the edited information is pushed back into their WordPress account. Is this possible?

Hello, <<FIRST NAME HERE>>
Preferred eating style (see list above if the user wants to edit)
Allergies
Last recorded weight (free form field), Darren, it would be ideal to record each time they change this, along with the date, so that we can show their weight on a graph (in a future version, not v1)



QUESTION




LOBOS INPUTS 

How are you feeling today (optional)? <check all that apply>> Darren, I want to collect this information for a future version of Lobos (their status tied to date)
No GLP-1-related symptoms
GLP-1 related nausea
GLP-1-related constipation and bloating

Meal Type <drop down>>
Breakfast
Lunch
Dinner
Side
Dessert
Snack 
1-Day (all meals + snacks)
3-Days (all meals + snacks)
Meal Type <drop down>>
Breakfast
Lunch
Dinner
Side
Dessert
Snack 
1-Day (all meals + snacks)
3-Days (all meals + snacks)

Eating Style (single select) <<DARREN - The user already entered this info in preferences. The problem to solve here in the UI is to give the user variability in meal types if they pick more than one meal. What do you think? >>
No Preference – default
Keto – Low-carb, high-fat approach that suppresses appetite via ketosis
Paleo – Whole-food, ancestral eating pattern with moderate carbs and protein
Mediterranean – Balanced intake of fats, fiber, and lean proteins with a heart-healthy focus
Green Mediterranean – Plant-forward Mediterranean with added polyphenols and minimal meat
Whole Food Plant-Based (WFPB) – 100% plant-based, high-fiber, minimally processed nutrition
Vegetarian – Plant-based with inclusion of dairy and/or eggs, no meat or fish
Flexitarian – Mostly plant-based with occasional inclusion of animal protein
Pegan – Hybrid of Paleo and Vegan principles, low-grain, anti-inflammatory
Whole30 – 30-day elimination protocol removing sugar, grains, dairy, and legumes
Vegan – 100% plant-based; excludes all animal products including dairy, eggs, and honey
Low-FODMAP - definition limits poorly absorbed carbohydrates that can trigger bloating, gas, pain, and diarrhea, especially in people with IBS.




<<DARREN UI DIRECTION - The next fields only show up if the user selects ADVANCED INPUTS>>

HEADLINE: ADVANCED INPUTS
<<DARREN - These are all optional>>
Dietary Preference <<DARREN, Checkbox - allow multi select>> 
No Preference (default)
High-Protein
Low-Carb Diet
Gluten-Free Diet
Dairy-Free
Low Glycemic Index
Low Sodium
Dish Type (pick list - users want a quick food format selection)
None (default)
 Bake
 Bowl
 Casserole
Flatbread
Grain Bowl
 Pasta
Salad
Sandwich
Smoothie
Soup
Stew
Stir-Fry
Wrap
Activity Level 
Little to no exercise
Light exercise (1–3 days per week)
Moderate exercise (3–5 days per week)
Heavy exercise (6–7 days per week)
Very heavy exercise (twice per day, extra heavy workouts)
Macros
50% C / 30% P / 20% F – Balanced Carb Focus: For active users, light-to-moderate exercisers, or plant-forward eaters who tolerate carbs well.


40% C / 40% P / 20% F – Protein-Enhanced Lean: Ideal for GLP-1 users looking to optimize satiety and muscle support without high fat.


30% C / 40% P / 30% F – Low-Carb, High-Protein: Supports appetite control, metabolic stability, and is GLP-1 aligned for taper or post-med.


40% C / 30% P / 30% F – Carb-Fat Balanced: Flexible for moderate activity or transition meals; good for Mediterranean or flexitarian styles.


30% C / 30% P / 40% F – Fat-Forward Low-Carb: For low-carb/keto users or those seeking higher healthy fats for energy and fullness.


Preparation <<DARREN drop down, select one>>
No preference (default)
5-Ingredient  
Quick (15 min and under)  
No Cook  
Are you experiencing any symptoms you’d like support with? (Max selection: 2) 
Nausea Relief – Gentle meals with light flavors and low fat to ease queasiness and digestion.
Constipation Support – Fiber-forward meals with hydration-promoting ingredients to support regularity.
Fullness Support – High-satiety meals that emphasize protein, fiber, and low energy density.
Low Appetite – Easy-to-eat meals that are soft, energy-dense, and nutrient-packed.
Bloating Relief – Meals designed with low-FODMAP ingredients to reduce digestive discomfort.
Muscle Maintenance – Protein-rich meals with recovery-supporting nutrients to preserve lean mass.

Tailor recipes to my GLP-1 status <<DARREN - This may require more advanced coding. If we can add it, it will help us stand out in the market. See the logic for each of these below>>

Just Starting (Weeks 1–6)
On Medication (Stable Phase)
Tapering Off / Lowering Dose
Off Medication / Post-GLP-1
<<DARREN BACKEND LOGIC FOR TAILORING RECIPES TO GLP-1 STATUS FIELD>>
1. Just Starting (Weeks 1–6)
User Needs: Low appetite, nausea, texture sensitivity
Macro Priorities:
Protein-first
Low to moderate fat
Gentle fiber (not high volume)
 Eating Style Suggestions:
<<DARREN - If the user doesn’t select an eating style, we can use these. If the user does select an eating style it would supercede these>>

WFPB (gentle versions) – Soups, soft stews, low-fat blended meals


Vegetarian – Light dishes, egg-based or dairy protein options


Mediterranean – Light brothy dishes, poached fish, soft-cooked grains


Green-MED – Same as above, with added anti-inflammatory boost


Not recommended yet: Keto, Paleo, Whole30 (can be too heavy or rough-textured early on
Avoid or De-prioritize:
High-volume, very high-fiber meals (e.g., raw cruciferous-heavy salads)
Excess oil or spicy foods



2. On Medication (Stable Phase)
User Needs: Appetite may improve slightly, learning hunger cues
Macro Priorities:
Balanced fat-fiber-protein
Moderate volume
Support digestion and routine
 Eating Style Suggestions:
<<DARREN - If the user doesn’t select an eating style, we can use these. If the user does select an eating style it would supercede these>>

Mediterranean – Strong synergy with GLP-1, balanced and evidence-backed


Flexitarian – Promotes variety while meeting macro needs


Green-MED – Anti-inflammatory, high-fiber, satiety-focused


Keto or Pegan – If fat digestion is tolerated, can help suppress appetite


WFPB – Higher fiber meals for those with adjusted gut tolerance


Watch-outs:
Still limit high-fat and very large meals



3. Tapering Off / Lowering Dose
User Needs: Hunger may spike, cravings return, structure needed
 Macro Priorities:
High protein
High fiber
High-volume foods for satiety


 Eating Style Suggestions:
<<DARREN - If the user doesn’t select an eating style, we can use these. If the user does select an eating style it would supercede these>>

Keto – Suppresses appetite via ketosis; useful for hunger control


Paleo – High-protein, high-satiety, unprocessed and structured


Whole30 – Clean ingredients + habit focus


Green-MED – Anti-inflammatory, fiber-rich, helpful for satiety


WFPB – For plant-based users needing high-volume meals


Flexitarian – Can adapt macros while staying structured


Avoid or De-prioritize:
Low-volume snacks/meals (trigger hunger return)



4. Off Medication / Post-GLP-1
User Needs: Long-term hunger regulation, blood sugar stability, habit reinforcement
Macro Priorities:
High protein
Balanced macros
High fiber
Digestive and hormonal support


Eating Style Suggestions:
<<DARREN - If the user doesn’t select an eating style, we can use these. If the user does select an eating style it would supercede these>>
Green-MED – Combines fiber, anti-inflammatory compounds, and balance


Mediterranean – Time-tested structure and flexibility


WFPB – High-satiety, gut-supportive, metabolic repair


Flexitarian – Ideal transition bridge for most users


Pegan – Balanced, whole-food, blood sugar control


Vegetarian – Maintains structure for those used to plant-based eating



Emphasis:
Consistency, sustainability, blood sugar control, and enjoyment




 

✅ Symptom Logic for Developer (Backend Spec)

1. Nausea Relief
symptom_key: nausea

Include:


Simple, bland proteins (chicken breast, tofu, eggs, white fish)


Ginger, mint, broth-based recipes, rice


Cooked, soft vegetables (carrots, zucchini)


Avoid:


Spicy, acidic, fried, or greasy foods


Onions, garlic, citrus, strong fermented flavors


Preferred Recipe Tags:


Low-fat, gentle-digesting, anti-nausea


Macro Bias:


Low-to-moderate fat; moderate protein



2. Constipation Support
symptom_key: constipation

Include:


High-fiber foods (chia, flax, oats, lentils, leafy greens, berries)


Hydrating foods (cucumber, zucchini, soups)


Magnesium-rich (pumpkin seeds, spinach)


Avoid:


Low-fiber, highly processed ingredients


Excessive dairy or red meat


Preferred Recipe Tags:


High fiber, digestive support, stool regularity


Macro Bias:


Moderate fat, moderate carbs, high fiber



3. Fullness Support
symptom_key: fullness

Include:


High-volume, low-calorie foods (leafy greens, cabbage, broth-based soups)


Fiber + protein synergy (e.g. beans + quinoa, chicken + veggies)


Slow-digesting carbs (lentils, barley)


Avoid:


Ultra-processed carbs


High-calorie small-volume foods (cheese, oils, heavy cream)


Preferred Recipe Tags:


High satiety, volume eating, GLP-1 friendly


Macro Bias:


High protein, high fiber, moderate carbs



4. Low Appetite
symptom_key: low_appetite

Include:


Calorie-dense, soft-texture foods (smoothies, nut butters, eggs, Greek yogurt)


Flavorful but not overwhelming (herbed oils, mild spices)


Energy-dense add-ons (avocado, tahini, olive oil drizzle)


Avoid:


Bitter greens, dry lean meats, large volume meals


Preferred Recipe Tags:


Low volume, easy to eat, nutrient-dense


Macro Bias:


Higher fat, moderate protein, small volume



5. Bloating Relief
symptom_key: bloating

Include:


Low-FODMAP-friendly ingredients (zucchini, carrots, firm tofu, rice, eggs, citrus)


Peppermint, cucumber, fennel


Avoid:


Onions, garlic, legumes, dairy, wheat, cauliflower, Brussels sprouts


Preferred Recipe Tags:


Bloat-reducing, low FODMAP, gut-soothing


Macro Bias:


Balanced macros with ingredient filtering



6. Muscle Maintenance
symptom_key: muscle_maintenance

Include:


30g+ protein per meal: chicken, turkey, salmon, Greek yogurt, cottage cheese, lentils + grains


Leucine-rich: eggs, beef, whey, tempeh


Recovery-supportive: potassium (sweet potato), omega-3 (salmon), anti-inflammatory (turmeric)


Avoid:


Low-protein meals (<20g), sugary/refined carb meals


Preferred Recipe Tags:


Muscle-building, post-workout, strength-support


Macro Bias:


High protein, balanced carbs and fats



🧠 Implementation Notes
Each symptom can tag the recipe request with 2–3 backend rules:


include_ingredients


exclude_ingredients


preferred_tags


macro_profile_bias (optional)


The engine should filter out conflicting recipes (e.g., “nausea + bloating” should not return spicy lentil curry).


If 2 symptoms are selected, merge rules and resolve priority:


Conflicts resolved by soft exclusion (e.g. filter by lowest conflict score)


Use recipe scoring logic for best match


✅ 1. Final Algorithm Handling Instructions (Symptom Combinations)
🔁 Merge Rules When 2 Symptoms Are Selected
When a user selects two symptoms, the engine should:
Combine include_ingredients sets (union)


Combine exclude_ingredients sets (union)


Combine preferred_tags (weight-based scoring optional)


Respect macro_profile_bias only if both symptoms align (or default to user-selected macro split)


Example:
 ["nausea", "constipation"]
Include: ginger, broth, carrots, oats


Exclude: spicy, citrus, garlic


Result: recipes must meet all exclude criteria, and prioritize overlapping includes


⚠️ Conflict Handling (Built-in Flex Rules)
If a conflict arises (e.g., one symptom includes garlic, one excludes garlic), the exclude rule should override


Prioritize safety/symptom relief over completeness


Developer may implement a “conflict score” system to rank recipes based on how well they match both symptoms



✅ 2. Output Filtering Logic
Only return recipes that:
Do not contain any excluded ingredients


Contain ≥1 key included ingredient or match at least one preferred tag


If multiple matches remain, score higher the recipes with:


More tag matches


Closer macro alignment


Faster prep time (optional)



✅ 3. Developer Summary Checklist
Here’s a final summary block your dev can follow directly:

👨‍💻 Developer Build Requirements
Allow user to select up to 2 symptoms


Pass symptom selections as array: ["nausea", "bloating"]


Each symptom maps to:


include_ingredients: array


exclude_ingredients: array


preferred_tags: array


macro_profile_bias: optional string


When 2 symptoms selected:


Merge include_ingredients → UNION


Merge exclude_ingredients → UNION


Merge preferred_tags → UNION


If conflict in macros, fall back to user-selected macro profile


Remove any recipes with excluded ingredients


Score and rank recipes by match relevance:


Ingredient match


Tag match


Macro proximity (optional)


Return final sorted result set



If your developer follows this structure, the algorithm will accurately serve symptom-specific recipes with up to 2 symptoms selected, while still aligning with GLP-1 needs and recipe generation logic.