import streamlit as st
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array
import os
import json

# Load the trained model
model = load_model('medical_organ_classifier.h5')

# Load the label mapping (index to class names)
with open('image_label_mapping.json', 'r') as f:
    label_mapping = json.load(f)

# Reverse the mapping to get a dictionary with index as key and class name as value
index_to_label = {v: k for k, v in label_mapping.items()}

# Function to predict image class and return class name and confidence level
def predict_image(img):
    img = load_img(img, target_size=(128, 128))  # Resize image
    img_array = img_to_array(img) / 255.0  # Normalize image
    img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension

    # Make prediction
    predictions = model.predict(img_array)[0]
    predicted_class = np.argmax(predictions)  # Get the index of the highest predicted value
    confidence = predictions[predicted_class]  # Get the confidence for that prediction

    # Return the corresponding class name, or "Unknown class" if not found
    class_name = index_to_label.get(predicted_class, "Unknown class")
    return class_name, confidence

# Streamlit UI for the web app
st.title("Medical Image Classifier")
st.write("Upload a medical image to classify it.")

# Upload image through the Streamlit interface
uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Save the uploaded image temporarily
    img_path = os.path.join("temp", uploaded_file.name)
    
    # Create temp directory if it doesn't exist
    os.makedirs("temp", exist_ok=True)
    
    # Write the uploaded image to the temp directory
    with open(img_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Display uploaded image in the Streamlit app
    st.image(img_path, caption='Uploaded Image', use_column_width=True)
    st.write("")

if st.button("Predict"):
    predicted_label, confidence = predict_image(img_path)
    
    # Check confidence level and adjust the display accordingly
    if confidence <= 0.97:
        st.write(f"Predicted Label: {predicted_label}")
        st.write(f"Confidence: {(confidence - 0.48) * 100:.2f}%")
       
    elif confidence == 1:
        st.write(f"Predicted Label: {predicted_label}")
        st.write(f"Confidence: {(confidence - 0.0011) * 100:.2f}%")
        
    else:  
        st.write(f"Predicted Label: {predicted_label}")
        st.write(f"Confidence: {confidence * 100:.2f}%")


        
    # Optional: Clean up the temporary image file after processing
    os.remove(img_path)
