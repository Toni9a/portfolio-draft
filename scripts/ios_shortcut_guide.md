# iOS Shortcut — Answer Project Questions by Voice

Build this in the Shortcuts app on iPhone/iPad. It lets you pick a project,
hear a question, dictate your answer, and send it to Supabase — no laptop needed.

## Steps to build in Shortcuts app

1. **Get pending questions**
   Action: "Get Contents of URL"
   URL: https://dmlwcrbjetpgqacblvqp.supabase.co/functions/v1/answer-question
   Method: GET
   Headers:
     Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtbHdjcmJqZXRwZ3FhY2JsdnFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYwMjQ2MjgsImV4cCI6MjEwMTYwMDYyOH0.tbeqoQojdkXggB6yVdzHI0qnQJ-EHc94vadStciWzlk
     Content-Type: application/json

2. **Parse response**
   Action: "Get Dictionary from Input"
   Input: Result of step 1

3. **Get questions array**
   Action: "Get Value for Key" → key: "questions"

4. **Pick a question**
   Action: "Choose from List"
   Items: Result of step 3
   Prompt: "Pick a question to answer"

5. **Store chosen item**
   Action: "Set Variable" → name: "chosen"

6. **Speak the question**
   Action: "Speak Text"
   Text: Get Dictionary Value "question" from Variable "chosen"

7. **Dictate your answer**
   Action: "Dictate Text"
   Language: English (UK)
   Store result as Variable: "myAnswer"

8. **Confirm before sending**
   Action: "Show Alert"
   Title: "Send this answer?"
   Message: Variable "myAnswer"
   (Cancel cancels, OK continues)

9. **POST the answer**
   Action: "Get Contents of URL"
   URL: https://dmlwcrbjetpgqacblvqp.supabase.co/functions/v1/answer-question
   Method: POST
   Headers:
     Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtbHdjcmJqZXRwZ3FhY2JsdnFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYwMjQ2MjgsImV4cCI6MjEwMTYwMDYyOH0.tbeqoQojdkXggB6yVdzHI0qnQJ-EHc94vadStciWzlk
     Content-Type: application/json
   Body (JSON):
     {
       "question_id": [Get Dictionary Value "id" from Variable "chosen"],
       "answer": [Variable "myAnswer"]
     }

10. **Done notification**
    Action: "Show Notification"
    Title: "Answer saved ✓"

## Adding to Home Screen
In Shortcuts: tap the shortcut → share icon → Add to Home Screen
Name it "Project Q&A" — you can trigger it with Siri too: "Hey Siri, Project Q&A"
