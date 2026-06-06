import os
import signal
import json
import asyncio
import discord
from typing import List, Optional

import state

class TextInputModal(discord.ui.Modal, title="Input Response"):
    """
    Description:
        A text input modal allowing freeform responses to agent questions.
    """
    text_input = discord.ui.TextInput(
        label="Your Answer",
        style=discord.TextStyle.paragraph,
        placeholder="Enter your response here...",
        required=True
    )
    
    def __init__(self, future: asyncio.Future):
        """
        Description:
            Initializer for TextInputModal.
        Usage:
            modal = TextInputModal(future)
        Usage Example:
            m = TextInputModal(asyncio.Future())
        """
        super().__init__()
        self.future = future
        
    async def on_submit(self, interaction: discord.Interaction):
        """
        Description:
            Handles submission of the text response.
        """
        await interaction.response.defer()
        if not self.future.done():
            self.future.set_result({
                "selected_option_ids": [],
                "freeform_response": self.text_input.value,
                "skipped": False
            })

class DiscordInteractionView(discord.ui.View):
    """
    Description:
        A multiple choice interactive view for agent questions.
    """
    def __init__(self, request_id: str, question_idx: int, options: List[dict], is_multi_select: bool = False, timeout: float = 300.0):
        """
        Description:
            Initializer for DiscordInteractionView.
        Usage:
            view = DiscordInteractionView(request_id, question_idx, options, is_multi_select)
        Usage Example:
            v = DiscordInteractionView("req-1", 0, [{"id": "a", "text": "Opt A"}])
        """
        super().__init__(timeout=timeout)
        self.request_id = request_id
        self.question_idx = question_idx
        self.options = options
        self.is_multi_select = is_multi_select
        self.future = state.pending_interactions[request_id]
        self.selected_ids = []
        
        for opt in options:
            btn = discord.ui.Button(
                label=opt['text'][:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"opt_{question_idx}_{opt['id']}"
            )
            btn.callback = self.make_callback(opt['id'])
            self.add_item(btn)
            
        skip_btn = discord.ui.Button(label="Skip/Skip All ➡️", style=discord.ButtonStyle.grey, custom_id="btn_skip")
        skip_btn.callback = self.skip_callback
        self.add_item(skip_btn)

    def make_callback(self, opt_id: str):
        """
        Description:
            Creates callback functions for choice options.
        Usage:
            cb = self.make_callback("opt-1")
        Usage Example:
            btn.callback = self.make_callback("opt-1")
        """
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            if not self.is_multi_select:
                if not self.future.done():
                    self.future.set_result({
                        "selected_option_ids": [opt_id],
                        "freeform_response": "",
                        "skipped": False
                    })
                self.stop()
            else:
                if opt_id in self.selected_ids:
                    self.selected_ids.remove(opt_id)
                else:
                    self.selected_ids.append(opt_id)
        return callback

    async def skip_callback(self, interaction: discord.Interaction):
        """
        Description:
            Callback for skip buttons.
        """
        await interaction.response.defer()
        if not self.future.done():
            self.future.set_result({
                "selected_option_ids": [],
                "freeform_response": "",
                "skipped": True
            })
        self.stop()

    async def on_timeout(self) -> None:
        """
        Description:
            Handles timeout events.
        """
        if not self.future.done():
            self.future.set_result({
                "selected_option_ids": [],
                "freeform_response": "",
                "skipped": True
            })

class DiscordFreeformInteractionView(discord.ui.View):
    """
    Description:
        A freeform response view offering skip or type buttons.
    """
    def __init__(self, request_id: str, timeout: float = 300.0):
        """
        Description:
            Initializer for DiscordFreeformInteractionView.
        """
        super().__init__(timeout=timeout)
        self.request_id = request_id
        self.future = state.pending_interactions[request_id]
        
    @discord.ui.button(label="Type Answer 📝", style=discord.ButtonStyle.green, custom_id="btn_type_answer")
    async def type_answer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Description:
            Displays the text modal.
        """
        modal = TextInputModal(self.future)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Skip ➡️", style=discord.ButtonStyle.grey, custom_id="btn_skip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Description:
            Skips the current question.
        """
        await interaction.response.defer()
        if not self.future.done():
            self.future.set_result({
                "selected_option_ids": [],
                "freeform_response": "",
                "skipped": True
            })
        self.stop()
        
    async def on_timeout(self) -> None:
        """
        Description:
            Handles timeout.
        """
        if not self.future.done():
            self.future.set_result({
                "selected_option_ids": [],
                "freeform_response": "",
                "skipped": True
            })

class DiscordApprovalView(discord.ui.View):
    """
    Description:
        A view prompting the user for command execution approval.
    """
    def __init__(self, request_id: str, show_always_allow: bool = True, timeout: float = 300.0):
        """
        Description:
            Initializer for DiscordApprovalView.
        """
        super().__init__(timeout=timeout)
        self.request_id = request_id
        self.future = state.pending_approvals[request_id]
        if not show_always_allow:
            self.remove_item(self.always_allow_button)

    async def on_timeout(self) -> None:
        """
        Description:
            Rejects on timeout.
        """
        if not self.future.done():
            self.future.set_result("deny")

    @discord.ui.button(label="Approve Once ✅", style=discord.ButtonStyle.green, custom_id="btn_approve_once")
    async def approve_once_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Description:
            Approves tool execution once.
        """
        await interaction.response.defer()
        if not self.future.done():
            self.future.set_result("approve")
        self.stop()

    @discord.ui.button(label="Allow for Project 📁", style=discord.ButtonStyle.blurple, custom_id="btn_allow_project")
    async def allow_project_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Description:
            Approves tool execution for the project.
        """
        await interaction.response.defer()
        if not self.future.done():
            self.future.set_result("allow_project")
        self.stop()

    @discord.ui.button(label="Always Allow 🌐", style=discord.ButtonStyle.blurple, custom_id="btn_always_allow")
    async def always_allow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Description:
            Approves tool execution globally.
        """
        await interaction.response.defer()
        if not self.future.done():
            self.future.set_result("always_allow")
        self.stop()

    @discord.ui.button(label="Deny ❌", style=discord.ButtonStyle.red, custom_id="btn_deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Description:
            Denies tool execution.
        """
        await interaction.response.defer()
        if not self.future.done():
            self.future.set_result("deny")
        self.stop()

class DiscordPlanApprovalView(discord.ui.View):
    """
    Description:
        A view for user to approve implementation plans.
    """
    def __init__(self, convo_id: str, metadata_path: str, plan_path: str):
        """
        Description:
            Initializer for DiscordPlanApprovalView.
        """
        super().__init__(timeout=None)
        self.convo_id = convo_id
        self.metadata_path = metadata_path

    @discord.ui.button(label="Approve Plan 👍", style=discord.ButtonStyle.green, custom_id="btn_approve_plan")
    async def approve_plan(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Description:
            Accepts the plan and updates metadata.
        """
        try:
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r') as f:
                    data = json.load(f)
                data["requestFeedback"] = False
                data["approved"] = True
                with open(self.metadata_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                embed = interaction.message.embeds[0]
                embed.color = discord.Color.green()
                embed.add_field(name="🏁 Status", value="Approved 👍", inline=False)
                await interaction.message.edit(embed=embed, view=None)
                await interaction.response.send_message("Plan approved! The agent will proceed once resumed.", ephemeral=True)
            else:
                await interaction.response.send_message("Error: Plan metadata file not found.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error approving plan: {e}", ephemeral=True)

class AgentMessageModal(discord.ui.Modal):
    """
    Description:
        A modal allowing users to send messages to a background agent.
    """
    def __init__(self, convo_id: str, goal_name: str):
        """
        Description:
            Initializer for AgentMessageModal.
        """
        super().__init__(title=f"Message {goal_name[:20]}")
        self.convo_id = convo_id
        self.goal_name = goal_name
        
        self.msg_input = discord.ui.TextInput(
            label="Message Content",
            style=discord.TextStyle.long,
            placeholder="Type your message here...",
            required=True,
            max_length=1000
        )
        self.add_item(self.msg_input)

    async def on_submit(self, interaction: discord.Interaction):
        """
        Description:
            Submits the message to the agent using the bot's messaging system.
        """
        await interaction.response.defer(ephemeral=True)
        # Import dynamically to avoid circular import issues
        import bot
        success = bot.send_agent_message(self.convo_id, self.msg_input.value)
        if success:
            await interaction.followup.send(content=f"✅ Message sent to Agent session `{self.convo_id[:8]}`!", ephemeral=True)
        else:
            await interaction.followup.send(content="❌ Failed to deliver message to the agent.", ephemeral=True)

class AgentDetailView(discord.ui.View):
    """
    Description:
        A view presenting actions for a specific agent session (messaging, terminating tasks).
    """
    def __init__(self, convo_id: str, goal_name: str, active_pids: List[int]):
        """
        Description:
            Initializer for AgentDetailView.
        """
        super().__init__(timeout=180.0)
        self.convo_id = convo_id
        self.goal_name = goal_name
        self.active_pids = active_pids
        
        self.btn_msg = discord.ui.Button(
            label="Send Message 💬", 
            style=discord.ButtonStyle.primary,
            custom_id="btn_agent_msg"
        )
        self.btn_msg.callback = self.send_message_callback
        self.add_item(self.btn_msg)
        
        self.btn_stop = discord.ui.Button(
            label="Stop Active Task 🛑", 
            style=discord.ButtonStyle.danger,
            disabled=len(active_pids) == 0,
            custom_id="btn_agent_stop"
        )
        self.btn_stop.callback = self.stop_task_callback
        self.add_item(self.btn_stop)

    async def send_message_callback(self, interaction: discord.Interaction):
        """
        Description:
            Shows message modal.
        """
        modal = AgentMessageModal(self.convo_id, self.goal_name)
        await interaction.response.send_modal(modal)

    async def stop_task_callback(self, interaction: discord.Interaction):
        """
        Description:
            Terminates active processes of this agent session.
        """
        await interaction.response.defer(ephemeral=True)
        killed_list = []
        failed_list = []
        for pid in self.active_pids:
            try:
                os.kill(pid, signal.SIGTERM)
                killed_list.append(pid)
            except Exception as e:
                failed_list.append(f"PID {pid} ({e})")
                
        if killed_list:
            msg = f"✅ Terminated active task process(es): {', '.join(map(str, killed_list))}"
            if failed_list:
                msg += f"\n⚠️ Failed to terminate: {', '.join(failed_list)}"
        else:
            msg = f"❌ Failed to terminate processes: {', '.join(failed_list)}"
            
        await interaction.followup.send(content=msg, ephemeral=True)
        # Import dynamically to update the dashboard
        import bot
        await bot.update_dashboard()

class AgentSpawnModal(discord.ui.Modal):
    """
    Description:
        A modal allowing users to enter a prompt to spawn a new agent.
    """
    def __init__(self, project_name: str):
        """
        Description:
            Initializer for AgentSpawnModal.
        """
        super().__init__(title=f"Spawn in {project_name[:20]}")
        self.project_name = project_name
        
        self.prompt_input = discord.ui.TextInput(
            label="Agent Goal/Prompt",
            style=discord.TextStyle.long,
            placeholder="Describe what task the agent should perform...",
            required=True,
            max_length=1000
        )
        self.add_item(self.prompt_input)

    async def on_submit(self, interaction: discord.Interaction):
        """
        Description:
            Submits prompt and spawns agent task.
        """
        await interaction.response.defer(ephemeral=True)
        prompt = self.prompt_input.value
        # Import dynamically to start task
        import bot
        asyncio.create_task(bot.run_spawned_agent(prompt, interaction.channel, self.project_name))
        await interaction.followup.send(content=f"🚀 Spawning agent task for `{self.project_name}`: *{prompt}*", ephemeral=True)
