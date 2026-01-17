import streamlit as st
from PIL import Image

from MealAgent.execution import MealPlannerAgent
# main llm

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="ChefGPT Luxe", page_icon="🥑", layout="wide")

# --- 2. STYLING (GLASSMORPHISM & CARDS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;600&display=swap');
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    
    .navbar {
        display: flex; justify-content: space-between; align-items: center;
        background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px);
        padding: 15px 50px; border-radius: 0 0 30px 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 40px;
    }
    .nav-logo { font-family: 'Playfair Display', serif; font-size: 28px; color: #1e1e1e; }
    
    .main-card {
        background: rgba(255, 255, 255, 0.95);
        padding: 40px; border-radius: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    .pill {
        display: inline-block; background: #ff4b4b; color: white;
        padding: 5px 15px; border-radius: 50px; margin: 5px;
        font-size: 0.8rem; font-weight: bold;
    }
    .store-item {
        color: #d9534f; font-weight: 600; font-style: italic;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. NAVBAR ---
st.markdown("""
    <div class="navbar">
        <div class="nav-logo"> ChefGPT Luxe</div>
        <div style="display: flex; gap: 30px; font-weight: 600;">
            <span>Inventory</span><span>Recipes</span><span>Pro</span>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- 4. APP STATE MANAGEMENT ---
if "step" not in st.session_state:
    st.session_state.step = "input"

def change_step(new_step):
    st.session_state.step = new_step

# --- 5. MAIN PAGE: INPUT & UPLOAD ---
if st.session_state.step == "input":
    st.markdown("<h1 style='text-align: center; font-family: Playfair Display; font-size: 3.5rem;'>What's cooking today?</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 5, 1])
    
    with col2:
        with st.container(border=True):
            st.markdown("<div class='main-card'>", unsafe_allow_html=True)
            u_left, u_right = st.columns([1, 1.2])
            
            with u_left:
                st.markdown("### 📸 1. Your Ingredients")
                uploaded_file = st.file_uploader("Upload fridge photo", type=['jpg', 'png', 'jpeg'], label_visibility="collapsed")
                
                if uploaded_file:
                    img = Image.open(uploaded_file)
                    st.image(img, caption="Detected Ingredients", use_container_width=True)
                else:
                    st.info("Upload a photo to see the preview.")

            with u_right:
                st.markdown("### ✍️ 2. Preferences")
                st.text_area("Dietary instructions", placeholder="e.g. 'High protein, no dairy, use the chicken first.'", height=150)
                
                g1, g2 = st.columns(2)
                with g1: st.selectbox("Style", ["Muscle Gain", "Weight Loss", "Quick Meal"])
                with g2: st.select_slider("Time", ["15m", "30m", "60m"])

            st.write("---")
            if st.button("✨ Craft My Recipe", use_container_width=True, type="primary"):
                if uploaded_file:
                    change_step("clarify")
                    st.rerun()
                else:
                    st.warning("Please upload a photo first!")
            st.markdown("</div>", unsafe_allow_html=True)

# --- 6. CLARIFY STATE (INTERRUPT) ---
elif st.session_state.step == "clarify":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🧐 Quick Question")
        st.image("https://images.unsplash.com/photo-1518977676601-b53f02ac6d31?w=400", width=200)
        st.info("The AI detected something that looks like **Potatoes**, but it's a bit blurry.")
        st.text_input("Please clarify:", placeholder="e.g. They are Sweet Potatoes")
        
        if st.button("Generate Recipe →", use_container_width=True, type="primary"):
            change_step("recipe")
            st.rerun()

# --- 7. RECIPE STATE (FINAL RESULT) ---
elif st.session_state.step == "recipe":
    st.markdown("<h1 style='text-align: center; font-family: Playfair Display;'>Mediterranean Protein Sauté</h1>", unsafe_allow_html=True)
    
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    r_left, r_right = st.columns([1, 1.5])
    
    with r_left:
        st.image("https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600", use_container_width=True)
        
        st.markdown("### 📦 In Your Kitchen")
        st.markdown('<span class="pill">Chicken Breast</span><span class="pill">Fresh Spinach</span><span class="pill">Garlic Cloves</span>', unsafe_allow_html=True)
        
        st.markdown("### 🛒 Grab from Store")
        st.markdown("""
            <p class='store-item'>• Heavy Cream (for the sauce)</p>
            <p class='store-item'>• Shredded Parmesan</p>
            <p class='store-item'>• Fresh Lemon</p>
        """, unsafe_allow_html=True)

    with r_right:
        st.markdown("### 🍳 Cooking Instructions")
        st.write("**Step 1:** Pat chicken dry and season with salt and pepper.")
        st.write("**Step 2:** Sauté garlic in a hot pan, then add chicken for 6-8 mins.")
        st.write("**Step 3:** Stir in the cream and parmesan from the store until thickened.")
        st.write("**Step 4:** Toss in spinach until wilted. Squeeze lemon to finish.")
        
        st.divider()
        
        # --- FUNCTIONAL BUTTONS ---
        b1, b2 = st.columns(2)
        with b1:
            if st.button("✅ Approve Recipe", use_container_width=True, type="primary"):
                st.balloons()
                st.success("Recipe saved to your meal plan!")
        with b2:
            # REJECT BUTTON: Resets the state back to input
            if st.button("❌ Reject / Restart", use_container_width=True):
                change_step("input")
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)




