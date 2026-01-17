# states
from typing import List, Dict, Any, Optional, Annotated, Union, Sequence
from pydantic import BaseModel, Field
import operator
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage, AIMessage
# define any util functions here
import glob as gl
import base64
import datetime
from langgraph.types import interrupt, Command

from utils import logger


class Message(BaseModel):
    role: str  # e.g., 'Human', 'AI', 'System'
    content: str

class CurrentConversationInput(BaseModel):
    goal: Optional[str] = None
    instructions: Optional[str] = None
    images: Optional[List[str]] = None

class Clarification(BaseModel):
    question: Optional[str] = None

class ImageProcessingOutput(BaseModel):
    image_name: Optional[str] = None
    image_description: Optional[str] = None
    clarification_needed: Optional[bool] = None
    clarification_question: Optional[Clarification] = None

class Ingredient(BaseModel):
    ingredient_name: Optional[str] = None

class MealRecipe(BaseModel):
    meal_name: Optional[str] = None
    meal_description: Optional[str] = None
    ingredients_list: Optional[List[Ingredient]] = None
    what_you_have: Optional[List[str]] = None
    what_you_need_to_buy: Optional[List[str]] = None
    duration_of_the_meal: Optional[str] = None
    cooking_steps: Optional[List[str]] = Field(
        default_factory=list,
        description="Step-by-step instructions on how to prepare the meal"
    )

    approve: Optional[bool] = None


class ExecutionTime(BaseModel):
    start_time: Optional[str] = None  # Could be datetime.datetime
    end_time: Optional[str] = None    # Could be datetime.datetime
    execution_time: Optional[str] = None # Duration as a string, e.g., '1h 30m'

class AgentState(BaseModel):
    messages: Annotated[Sequence[BaseMessage], operator.add] = Field(default_factory=list)
    current_conversation_input: Optional[CurrentConversationInput] = None
    image_processing_output: ImageProcessingOutput = Field(default_factory=ImageProcessingOutput) # Corrected default_factory
    meal_recipe: Optional[MealRecipe] = None
    errors: List[str] = Field(default_factory=list)
    retry_policy: int = 2
    clarification: Optional[Clarification] = None
    need_human: bool = False
    execution_time: Optional[ExecutionTime] = None
    current_node_name: Optional[str] = None


class MealPlannerAgent:

    def __init__(self, model):
        self.model = model
        self.logger = logger.bind(MealPlannerAgent.__name__)


    def generate_image_blocks_from_path(self, path: str) -> dict:
        self.logger.info("generating image block")
        with open(path, "rb") as image_file:
            self.logger.info("reading file")
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
            self.logger.info("base 64 generated successfuly")
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            }

    # define nodes

    def process_images(self, state: AgentState) -> AgentState:
        self.logger.info("processing image")

        state.current_node_name = "process_images"

        state.execution_time["start_time"] = datetime.datetime.now()

        if not state.current_conversation_input or not state.current_conversation_input.images:
            state.errors.append("No images provided")
            return state

        images = state.current_conversation_input.images

        # Prepare structured output model
        llm_with_structured_output = self.model.with_structured_output(ImageProcessingOutput)

        # Generate the image content blocks
        image_blocks = [
            self.generate_image_blocks_from_path(image)
            for image in images
        ]

        system_prompt = SystemMessage(content="""

        You are a meal-planning assistant with strong visual understanding skills.

        Your role is to analyze images related to food, meals, and cooking ingredients.
        Most images will be photos of ingredients, prepared meals, or food items.

        Your task is to accurately understand what is shown in each image, describe it clearly,
        and determine whether additional clarification from the user is required.
        Do not make assumptions when the image is unclear or ambiguous.

        """)

        human_message = HumanMessage(content=[
            {
                "type": "text",
                "text": """
                  Analyze the provided image.

                  Based on what you can see, return:
                  - The name of the meal or ingredient shown (if identifiable)
                  - A brief description of what the image contains
                  - Whether clarification from the user is needed

                  If the image is unclear, incomplete, or could represent multiple things,
                  set clarification_needed to true and ask a clear, specific question
                  to help identify the meal or ingredients.
                  """
            },
            *image_blocks
        ]
        )

        # Add messages to a temporary list to send to LLM
        # Note: If your state uses 'add_messages', we return these later
        current_messages = state.messages + [system_prompt, human_message]

        try:
            # FIX: Just pass the messages list. No **image_blocks here.
            output = llm_with_structured_output.invoke(current_messages)



            # Update state fields - Wrap the single output in a list
            state.image_processing_output = output
            state.messages = current_messages  # Or return as a dict if using Graph
            self.logger.info("processing image successful")
        except Exception as e:
            self.logger.error(f"processing image failed {e}")
            state.errors.append(str(e))

        return state



    def image_clarification_node(self, state: AgentState) -> AgentState:
        """Simplified clarification node that just interrupts."""
        self.logger.info("image decision node")
        # Always interrupt for clarification
        user_response = interrupt({
            "instruction": "Image clarification needed",
            "clarification_question": state.image_processing_output.clarification_question
        })

        if user_response.get("type") == "image_url":
            # Create a clean update for the nested field
            new_input = state.current_conversation_input.model_copy()
            new_input.images = [user_response.get("url")]

            return {
                "current_conversation_input": new_input,
                "need_human": False
            }
        else:
            return {
                "messages": [HumanMessage(content=user_response.get("text", ""))],
                "need_human": False
            }

    def approve_reject_meal(self,state: AgentState) -> AgentState:
        """ add more context to blury images"""

        self.logger.info("approve meal node")

        meal_recipe_data = {}
        if state.meal_recipe:
            meal_recipe_data = {
                "meal_name": state.meal_recipe.meal_name,
                "meal_description": state.meal_recipe.meal_description,
                "ingredients_list": state.meal_recipe.ingredients_list,
                "what_you_have": state.meal_recipe.what_you_have,
                "what_you_need_to_buy": state.meal_recipe.what_you_need_to_buy,
                "duration_of_the_meal": state.meal_recipe.duration_of_the_meal,
                "cooking_steps": state.meal_recipe.cooking_steps
            }

        value = interrupt(
            {
                "instruction": "Could you please verify the below",
                "clarification_question": meal_recipe_data,
            }
        )

        if state.meal_recipe:  # Ensure meal_recipe exists before setting approve
            if value == "approve":
                state.meal_recipe.approve = True
                state.messages.append(HumanMessage(content="I have approved this meal"))
                state.need_human = False
                state.clarification = None
                return state
            elif value == "reject":
                state.meal_recipe.approve = False
                state.messages.append(HumanMessage(content="I have rejected this meal.Please generate another one"))
                state.need_human = False
                state.clarification = None
                return state
        else:
            state.messages.append(HumanMessage(content="No meal recipe was available to approve/reject."))
            state.need_human = False
            state.clarification = None

        return state

    # decision node
    def decision_node(self, state: AgentState) -> AgentState:
        """ add more context to blury images"""

        if state.image_processing_output.clarification_needed:
            return "image_clarification_node"
        else:
            return "generate_meal_recipe"

    # decide if we are supposed to regenerate another meal or not
    def regenerate_meal(self, state: AgentState) -> AgentState:
        """ regenerate meal"""
        user_response = interrupt({
            "instruction": "Approve or reject meal",
            "meal": state.meal_recipe
        })

        # Check if meal_recipe is None or if it was explicitly rejected
        if state.meal_recipe is None or user_response.lower() == "False".lower():
            return "generate_meal_recipe"
        else:
            return "END"

    def generate_meal_recipe(self, state: AgentState) -> AgentState:
        self.logger.info("in generate meal recipe node")
        if isinstance(state.image_processing_output, list):
            inventory_items = [f"{item.image_name}: {item.image_description}" for item in state.image_processing_output]
        else:
            inventory_items = [
                f"{state.image_processing_output.image_name}: {state.image_processing_output.image_description}"]

        inventory_str = "\n".join(inventory_items)
        llm_chef = self.model.with_structured_output(MealRecipe)

        system_prompt = SystemMessage(content="""
        You are a professional Resourceful Chef.
        Your goal is to suggest ONE meal plan based on the ingredients provided.

        CRITICAL: You must provide clear, step-by-step cooking instructions in the 'cooking_steps' field.

        Logic:
        - Use 'what_you_have' for items found in the image.
        - Use 'what_you_need_to_buy' for missing essentials.
        - Ensure the recipe fits the user's time constraints.
        """)

        human_prompt = f"""
        User Goal: {state.current_conversation_input.goal}
        Extra Instructions: {state.current_conversation_input.instructions}

        Inventory detected in photos:
        {inventory_str}
        """

        try:
            recipe = llm_chef.invoke([system_prompt, HumanMessage(content=human_prompt)])
            state.meal_recipe = recipe
            self.logger.info(
                "recipe generated"
            )
        except Exception as e:
            self.logger.error(
                f"recipe generation failed {e}"
            )
            state.errors.append(f"Chef Error: {str(e)}")

        return state


    def build_graph(self):
        from langgraph.graph import StateGraph, START, END
        from langgraph.checkpoint.memory import InMemorySaver
        # Create the graph
        workflow = StateGraph(AgentState)

        # Add Nodes
        workflow.add_node("process_images", self.process_images)
        workflow.add_node("generate_meal_recipe", self.generate_meal_recipe)
        workflow.add_node("image_clarification_node", self.image_clarification_node)

        # Define Edges
        workflow.add_edge(START, "process_images")

        # define a conditional edge
        workflow.add_conditional_edges(
            "process_images",
            self.decision_node,
            {
                "image_clarification_node": "image_clarification_node",
                "generate_meal_recipe": "generate_meal_recipe"
            }
        )

        # After clarification, we should go BACK to process_images
        # to reprocess with the new information
        workflow.add_edge("image_clarification_node", "process_images")

        workflow.add_conditional_edges(
            "generate_meal_recipe",
            self.regenerate_meal,
            {
                "generate_meal_recipe": "generate_meal_recipe",
                "END": END
            }
        )

        # Compile
        app = workflow.compile(checkpointer=InMemorySaver())


        return  app









