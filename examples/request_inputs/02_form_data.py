from nexios import NexiosApp

app = NexiosApp()


@app.post("/submit-form")
async def submit_form(req, res):
    form_data = await req.form_data
    return {"received": form_data}
