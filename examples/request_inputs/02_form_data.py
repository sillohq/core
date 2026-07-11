from sillo import silloApp

app = silloApp()


@app.post("/submit-form")
async def submit_form(req, res):
    form_data = await req.form_data
    return {"received": form_data}
