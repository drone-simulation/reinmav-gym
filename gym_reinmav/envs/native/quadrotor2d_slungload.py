#Copyright (C) 2018, by Jaeyoung Lim, jaeyoung@auterion.com
# 2D quadrotor slungload system environment using rate control inputs (continuous control)

#This is free software: you can redistribute it and/or modify
#it under the terms of the GNU Lesser General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
 
#This software package is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU Lesser General Public License for more details.

#You should have received a copy of the GNU Leser General Public License.
#If not, see <http://www.gnu.org/licenses/>.


import gym
from gym import error, spaces, utils
from math import cos, sin, pi, atan2
import numpy as np
from numpy import linalg
from gym.utils import seeding

class Quadrotor2DSlungload(gym.Env):
	metadata = {'render.modes': ['human']}
	def __init__(self):
		self.mass = 1.0
		self.load_mass = 0.1
		self.dt = 0.01
		self.g = np.array([0.0, -9.8])

		self.state = None

		self.ref_pos = np.array([0.0, 0.0])
		self.ref_vel = np.array([0.0, 0.0])

		self.tether_length = 0.5

		# Conditions to fail the episode
		self.pos_threshold = 0.1
		self.vel_threshold = 0.1


		self.viewer = None
		self.quadtrans = None
		self.loadtrans = None
		self.reftrans = None
		self.x_range = 1.0
		self.steps_beyond_done = None

		self.action_space = spaces.Box(low=self.min_action, high=self.max_action,
                                       shape=(2,), dtype=np.float32)
		self.observation_space = spaces.Box(low=self.low_state, high=self.high_state,
                                        shape=(9,), dtype=np.float32)
		self.seed()
		self.reset()

	def seed(self, seed=None):
		self.np_random, seed = seeding.np_random(seed)
		return [seed]

	def step(self, action):
		thrust = action[0] # Thrust command
		w = action[1] # Angular velocity command

		state = self.state
		ref_pos = self.ref_pos
		ref_vel = self.ref_vel

		pos = np.array([state[0], state[1]]).flatten()
		att = np.array([state[2]]).flatten()
		vel = np.array([state[3], state[4]]).flatten()
		load_pos = np.array([state[5], state[6]]).flatten()
		load_vel = np.array([state[7], state[8]]).flatten()

		tether_vec = load_pos - pos
		unit_tether_vec = tether_vec / linalg.norm(tether_vec)

		if linalg.norm(tether_vec) >= self.tether_length :
			thrust_vec = thrust*np.array([cos(att+ pi/2), sin(att + pi/2)])
			load_acceleration = np.inner(unit_tether_vec, thrust_vec - self.mass * self.tether_length * np.inner(load_vel, load_vel)) * unit_tether_vec
			load_acceleration = (1/(self.mass + self.load_mass)) * load_acceleration + self.g
			load_vel = load_vel + load_acceleration * self.dt
			load_pos = load_pos + load_vel * self.dt + 0.5 * load_acceleration * self.dt * self.dt

			T = self.load_mass * linalg.norm(-self.g + load_acceleration) * unit_tether_vec

			slack = False

			# Quadrotor dynamics
			acc = thrust/self.mass  * np.array([cos(att + pi/2), sin(att + pi/2)]) + self.g + T/self.mass
			vel = vel + acc * self.dt
			pos = pos + vel * self.dt + 0.5 * acc * self.dt * self.dt
			att = att + w * self.dt

			# Enforce kinematic constraints
			load_direction = (load_pos - pos) / linalg.norm(load_pos - pos)
			load_pos = pos + load_direction * self.tether_length
			load_vel = load_vel - np.inner(load_vel - vel, load_direction) * load_direction


		else :
			T = np.array([0.0, 0.0])
			self.slack = True

			# Load dynamics
			load_acceleration = self.g
			load_vel = load_vel + load_acceleration * self.dt
			load_pos = load_pos + load_vel * self.dt + 0.5 * load_acceleration * self.dt * self.dt

			# Quadrotor dynamics
			acc = thrust/self.mass * np.array([cos(att + pi/2), sin(att + pi/2)]) + self.g
			vel = vel + acc * self.dt
			pos = pos + vel * self.dt + 0.5*acc*self.dt*self.dt
			att = att + w * self.dt

		self.state = (pos[0], pos[1], att, vel[0], vel[1], load_pos[0], load_pos[1], load_vel[0], load_vel[1])

		done =  linalg.norm(load_pos, 2) < -self.pos_threshold \
			and  linalg.norm(load_pos, 2) > self.pos_threshold \
			and linalg.norm(load_vel, 2) < -self.vel_threshold \
			and linalg.norm(load_vel, 2) > self.vel_threshold
		done = bool(done)

		if not done:
		    reward = (-linalg.norm(pos, 2))
		elif self.steps_beyond_done is None:
		    # Pole just fell!
		    self.steps_beyond_done = 0
		    reward = 1.0
		else:
		    if self.steps_beyond_done == 0:
		        logger.warn("You are calling 'step()' even though this environment has already returned done = True. You should always call 'reset()' once you receive 'done = True' -- any further steps are undefined behavior.")
		    self.steps_beyond_done += 1
		    reward = 0.0

		return np.array(self.state), reward, done, {}

	def control(self):
		Kp = -5.0
		Kv = -4.0
		tau = 0.1


		state = self.state
		ref_pos = self.ref_pos
		ref_vel = self.ref_vel

		pos = np.array([state[0], state[1]]).flatten()
		att = np.array([state[2]]).flatten()
		vel = np.array([state[3], state[4]]).flatten()
		load_pos = np.array([state[5], state[6]]).flatten()
		load_vel = np.array([state[7], state[8]]).flatten()

		error_pos = pos - self.ref_pos
		error_vel = vel - self.ref_vel
		# %% Calculate desired acceleration
		desired_acc = Kp * error_pos + Kv * error_vel + [0.0, 9.8]
		desired_att = atan2(desired_acc[1], desired_acc[0]) - pi/2
		error_att = att - desired_att
		w = (-1/tau) * error_att
		thrust = self.mass * linalg.norm(desired_acc, 2)

		action = np.array([thrust, w])

		return action 

	def reset(self):
		print("reset")
		self.state = np.array(self.np_random.uniform(low=-1.0, high=1.0, size=(9,)))
		return np.array(self.state)

	def render(self, mode='human', close=False):
		screen_width = 600
		screen_height = 400

		world_width = self.x_range*2
		scale = screen_width/world_width
		quadwidth = 80.0
		quadheight = 10.0
		ref_size = 5.0
		load_size = 5.0

		if self.viewer is None:
			from gym.envs.classic_control import rendering
			self.viewer = rendering.Viewer(screen_width, screen_height)
			# Draw drone
			l,r,t,b = -quadwidth/2, quadwidth/2, quadheight/2, -quadheight/2
			quad = rendering.FilledPolygon([(l,b), (l,t), (r,t), (r,b)])
			self.quadtrans = rendering.Transform()
			quad.add_attr(self.quadtrans)
			self.viewer.add_geom(quad)
			# Draw load
			load = rendering.make_circle(load_size)
			self.loadtrans = rendering.Transform()
			load.add_attr(self.loadtrans)
			load.set_color(0,0,1)
			self.viewer.add_geom(load)

			# Draw reference
			ref = rendering.make_circle(ref_size)
			self.reftrans = rendering.Transform()
			ref.add_attr(self.reftrans)
			ref.set_color(1,0,0)
			self.viewer.add_geom(ref)

		if self.state is None: return None

		state = self.state
		ref_pos = self.ref_pos
		ref_vel = self.ref_vel

		pos = np.array([state[0], state[1]]).flatten()
		att = np.array([state[2]]).flatten()
		vel = np.array([state[3], state[4]]).flatten()
		load_pos = np.array([state[5], state[6]]).flatten()
		load_vel = np.array([state[7], state[8]]).flatten()

		x = pos
		theta = att
		quad_x = x[0]*scale+screen_width/2.0 # MIDDLE OF CART
		quad_y = x[1]*scale+screen_height/2.0 # MIDDLE OF CART
		self.quadtrans.set_translation(quad_x, quad_y)
		self.quadtrans.set_rotation(theta)

		x_l = load_pos
		np.set_printoptions(precision=3)
		load_x = x_l[0]*scale+screen_width/2.0
		load_y = x_l[1]*scale+screen_height/2.0
		self.loadtrans.set_translation(load_x, load_y)


		y = self.ref_pos
		ref_x = y[0]*scale+screen_width/2.0
		ref_y = y[1]*scale+screen_height/2.0
		self.reftrans.set_translation(ref_x, ref_y)

		return self.viewer.render(return_rgb_array = mode=='rgb_array')

	def close(self):
		if self.viewer:
			self.viewer.close()
			self.viewer = None