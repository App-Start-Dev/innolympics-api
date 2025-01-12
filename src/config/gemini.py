import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-pro")


async def respond_to_message(message, first_message=False):
    if first_message:
        context = "You are a clinical psychologist with expertise in child development and behavioral health. You often conduct assessments, diagnose ASD, and provide therapy to help manage symptoms. You also help guide parents, teachers, and support workers on how to best interact with children with ASD. You are passionate about helping mothers and fathers understand their child's unique needs and strengths."
        instruction = "You will be given short questions coming from guardians, teachers, and support workers of the children with ASD. You must respond emphatetically and provide guidance on how to best interact with the child given a specific scenario. You also keep a document that contains your previous diagnoses of the child's current condition and the progress of the therapy. What follows is the specified document:"
        with open("diagnosis.md", "r", encoding="utf-8") as file:
            document = file.read()
        output = f"You are to answer the following question as if you are in a consultation with the mother of the child. Ensure that your answer is concise, easy to understand with as little jargon as possible, and actionable. The question is: {message}"
        prompt = f"""{context}\n\n{instruction}\n\n{document}\n\n{output}"""
    else:
        prompt = f"""You are a clinical psychologist with expertise in child development and behavioral health, 
        specializing in ASD (Autism Spectrum Disorder). Respond to the following question from a parent or caregiver 
        of a child with ASD. Be empathetic, clear, and provide actionable guidance.

        Question: {message}"""

    try:
        # Generate response using the model
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "I apologize, but I'm having trouble generating a response at the moment. Please try again later."
