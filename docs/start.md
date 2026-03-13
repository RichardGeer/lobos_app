this is where we left off
https://github.com/RichardGeer/lobos_app/blob/main/docs/PROJECT_CONTEXT.md
app.py
https://github.com/RichardGeer/lobos_app/blob/main/app.py
and preferences.py
https://github.com/RichardGeer/lobos_app/blob/main/preferences.py
and landing.html
https://github.com/RichardGeer/lobos_app/blob/main/templates/landing.html
my_recipe.html
https://github.com/RichardGeer/lobos_app/blob/main/templates/my_recipe.html
db
https://github.com/RichardGeer/lobos_app/blob/main/docs/currentDBschema.sql
and the rest in my git
https://github.com/RichardGeer/lobos_app

everything looks good with a few issues
for landing.html
clicking on complete onboarding cause 
Mar 13 15:32:00 ubunSvr24043LTS uvicorn[2257]: INFO:     192.168.57.1:63612 - "GET /my_recipe?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ3cC1zaW0iLCJzdWIiOiI4IiwiaWF0IjoxNzczNDE1NzQxLCJuYmYiOjE3NzM0MTU3NDEsImV4cCI6MTc3MzQxOTM0MSwidXNlcl9pZCI6IjgiLCJpZGVudGl0eSI6eyJlbWFpbCI6Im5pb2gyZWFzeUBnbWFpbC5jb20iLCJmaXJzdF9uYW1lIjoiVGVzdFVzZXIxIiwibGFzdF9uYW1lIjoiU3Vic2NyaWJlcjEiLCJyb2xlcyI6WyJhZG1pbmlzdHJhdG9yIl0sIm1lbWJlcnNoaXAiOnsibWVtYmVycHJlc3MiOnsidXNlcl9pZCI6OCwiZXhpc3RzIjp0cnVlLCJjb3VudCI6MSwibWVtYmVyc2hpcHMiOlt7ImlkIjoyNywidGl0bGUiOiJHTFAtMSBBY3Rpb24gUGxhbiBIdWIiLCJzdGF0dXMiOiJjb21wbGV0ZSJ9XX19fX0.5MGcJuELis6QL1hnTOMz5Oe8F0a1yhnuAuPYOYPgv14 HTTP/1.1" 404 Not Found
my_recipe.html
i remeber we used to have more fields like Meal Type, Macro reset and preparation which are now gone, can we get them back? also generate recipe does not seem to work any longer.





I think we pretty much finished the DB migration to a degree. 
let us work on the app.py and preferences.py 
https://github.com/RichardGeer/lobos_app/blob/main/app.py
https://github.com/RichardGeer/lobos_app/blob/main/preferences.py
to make the input for height now only inches to feet and inches, and the preferences before advanced input stated here in the desiredGoal.me
https://github.com/RichardGeer/lobos_app/blob/main/docs/desireGoals.me
so we can start generating some recipes for now. 


here is my 
https://github.com/RichardGeer/lobos_app/blob/main/templates/landing.html
and the github dir is 
https://github.com/RichardGeer/lobos_app/
can you make sure you have access to app.py if yes, check if your recommendation above is still valid.  once again unless you do have access to all the thing you need for your recommendation, if you don't, DO NOT MAKE ANY ASSUMEPTION as it will only make the work taking more time then it should. make sense?
