"""
Paper: "Fast and Accurate Image Super Resolution by Deep CNN with Skip Connection and Network in Network"

utility functions
"""

import configparser
import datetime
import logging
import math
import matplotlib.pyplot as plt
import numpy as np
import os
from os import listdir
from os.path import isfile, join
from scipy import misc
from sklearn.manifold import TSNE
import time
import tensorflow as tf
from PIL import Image

MARKERS = [['red', 100, 'o'], ['black', 100, 'x'], ['cyan', 100, 'd'], ['blue', 150, '1'], ['purple', 100, 's'],
           ['green', 100, 'v'], ['yellow', 100, 'o'], ['orange', 100, 'o'], ['magenta', 100, 'o'], ['pink', 100, 'o'],
           ['brown', 100, 'o'], ['darkgreen', 100, 'o']]
MARKERS2 = [['red', 300, 'o'], ['black', 300, 'x'], ['cyan', 300, 'd'], ['blue', 450, '1'], ['purple', 300, 's'],
           ['green', 300, 'v'], ['yellow', 300, 'o'], ['orange', 300, 'o'], ['magenta', 300, 'o'], ['pink', 300, 'o'],
           ['brown', 300, 'o'], ['darkgreen', 300, 'o']]

class Timer:
	def __init__(self, timer_count=100):
		self.times = np.zeros(timer_count)
		self.start_times = np.zeros(timer_count)
		self.counts = np.zeros(timer_count)
		self.timer_count = timer_count

	def start(self, timer_id):
		self.start_times[timer_id] = time.time()

	def end(self, timer_id):
		self.times[timer_id] += time.time() - self.start_times[timer_id]
		self.counts[timer_id] += 1

	def print(self):
		for i in range(self.timer_count):
			if self.counts[i] > 0:
				total = 0
				print("Average of %d: %s[ms]" % (i, "{:,}".format(self.times[i] * 1000 / self.counts[i])))
				total += self.times[i]
				print("Total of %d: %s" % (i, "{:,}".format(total)))


# utilities for save / load

class LoadError(Exception):
	def __init__(self, message):
		self.message = message


def make_dir(directory):
	if not os.path.exists(directory):
		os.makedirs(directory)

def delete_dir(directory):
	if os.path.exists(directory):
		clean_dir(directory)
		os.rmdir(directory)

def get_files_in_directory(path):
	if not path.endswith('/'):
		path = path + "/"
	file_list = [path + f for f in listdir(path) if (isfile(join(path, f)) and not f.startswith('.'))]
	return file_list


def remove_generic(path, __func__):
	try:
		__func__(path)
	except OSError as error:
		print("OS error: {0}".format(error))


def clean_dir(path):
	if not os.path.isdir(path):
		return

	files = os.listdir(path)
	for x in files:
		full_path = os.path.join(path, x)
		if os.path.isfile(full_path):
			f = os.remove
			remove_generic(full_path, f)
		elif os.path.isdir(full_path):
			clean_dir(full_path)
			f = os.rmdir
			remove_generic(full_path, f)


def set_logging(filename, stream_log_level, file_log_level, tf_log_level):
	stream_log = logging.StreamHandler()
	stream_log.setLevel(stream_log_level)

	file_log = logging.FileHandler(filename=filename)
	file_log.setLevel(file_log_level)

	logger = logging.getLogger()
	logger.handlers = []
	logger.addHandler(stream_log)
	logger.addHandler(file_log)
	logger.setLevel(min(stream_log_level, file_log_level))

	tf.logging.set_verbosity(tf_log_level)


def save_image(filename, image, print_console=False):
	if len(image.shape) >= 3 and image.shape[2] == 1:
		image = image.reshape(image.shape[0], image.shape[1])

	directory = os.path.dirname(filename)
	if directory != "" and not os.path.exists(directory):
		os.makedirs(directory)

	image = misc.toimage(image, cmin=0, cmax=255)  # to avoid range rescaling
	misc.imsave(filename, image)

	if print_console:
		print("Saved [%s]" % filename)


def save_image_data(filename, image):
	directory = os.path.dirname(filename)
	if directory != "" and not os.path.exists(directory):
		os.makedirs(directory)

	np.save(filename, image)
	print("Saved [%s]" % filename)


def convert_rgb_to_y(image, jpeg_mode=True, max_value=255.0):
	if len(image.shape) <= 2 or image.shape[2] == 1:
		return image

	if jpeg_mode:
		xform = np.array([[0.299, 0.587, 0.114]])
		y_image = image.dot(xform.T)
	else:
		xform = np.array([[65.481 / 256.0, 128.553 / 256.0, 24.966 / 256.0]])
		y_image = image.dot(xform.T) + (16.0 * max_value / 256.0)

	return y_image


def convert_rgb_to_ycbcr(image, jpeg_mode=True, max_value=255):
	if len(image.shape) < 2 or image.shape[2] == 1:
		return image

	if jpeg_mode:
		xform = np.array([[0.299, 0.587, 0.114], [-0.169, - 0.331, 0.500], [0.500, - 0.419, - 0.081]])
		ycbcr_image = image.dot(xform.T)
		ycbcr_image[:, :, [1, 2]] += max_value / 2
	else:
		xform = np.array(
			[[65.481 / 256.0, 128.553 / 256.0, 24.966 / 256.0], [- 37.945 / 256.0, - 74.494 / 256.0, 112.439 / 256.0],
			 [112.439 / 256.0, - 94.154 / 256.0, - 18.285 / 256.0]])
		ycbcr_image = image.dot(xform.T)
		ycbcr_image[:, :, 0] += (16.0 * max_value / 256.0)
		ycbcr_image[:, :, [1, 2]] += (128.0 * max_value / 256.0)

	return ycbcr_image


def convert_y_and_cbcr_to_rgb(y_image, cbcr_image, jpeg_mode=True, max_value=255.0):
	if len(y_image.shape) <= 2:
		y_image = y_image.reshape[y_image.shape[0], y_image.shape[1], 1]

	if len(y_image.shape) == 3 and y_image.shape[2] == 3:
		y_image = y_image[:, :, 0:1]

	ycbcr_image = np.zeros([y_image.shape[0], y_image.shape[1], 3])
	ycbcr_image[:, :, 0] = y_image[:, :, 0]
	ycbcr_image[:, :, 1:3] = cbcr_image[:, :, 0:2]

	return convert_ycbcr_to_rgb(ycbcr_image, jpeg_mode=jpeg_mode, max_value=max_value)


def convert_ycbcr_to_rgb(ycbcr_image, jpeg_mode=True, max_value=255.0):
	rgb_image = np.zeros([ycbcr_image.shape[0], ycbcr_image.shape[1], 3])  # type: np.ndarray

	if jpeg_mode:
		rgb_image[:, :, [1, 2]] = ycbcr_image[:, :, [1, 2]] - (128.0 * max_value / 256.0)
		xform = np.array([[1, 0, 1.402], [1, - 0.344, - 0.714], [1, 1.772, 0]])
		rgb_image = rgb_image.dot(xform.T)
	else:
		rgb_image[:, :, 0] = ycbcr_image[:, :, 0] - (16.0 * max_value / 256.0)
		rgb_image[:, :, [1, 2]] = ycbcr_image[:, :, [1, 2]] - (128.0 * max_value / 256.0)
		xform = np.array(
			[[max_value / 219.0, 0, max_value * 0.701 / 112.0],
			 [max_value / 219, - max_value * 0.886 * 0.114 / (112 * 0.587), - max_value * 0.701 * 0.299 / (112 * 0.587)],
			 [max_value / 219.0, max_value * 0.886 / 112.0, 0]])
		rgb_image = rgb_image.dot(xform.T)

	return rgb_image


def set_image_alignment(image, alignment):
	alignment = int(alignment)
	width, height = image.shape[1], image.shape[0]
	width = (width // alignment) * alignment
	height = (height // alignment) * alignment

	if image.shape[1] != width or image.shape[0] != height:
		image = image[:height, :width, :]

	if len(image.shape) >= 3 and image.shape[2] >= 4:
		image = image[:, :, 0:3]

	return image

def resize_image_by_pil(image, scale, resampling_method="bicubic"):
	width, height = image.shape[1], image.shape[0]
	new_width = int(width * scale)
	new_height = int(height * scale)

	if resampling_method == "bicubic":
		method = Image.BICUBIC
	elif resampling_method == "bilinear":
		method = Image.BILINEAR
	elif resampling_method == "nearest":
		method = Image.NEAREST
	else:
		method = Image.LANCZOS

	if len(image.shape) == 3 and image.shape[2] == 3:
		image = Image.fromarray(image, "RGB")
		image = image.resize([new_width, new_height], resample=method)
		image = np.asarray(image)
	elif len(image.shape) == 3 and image.shape[2] == 4:
		# the image may has an alpha channel
		image = Image.fromarray(image, "RGB")
		image = image.resize([new_width, new_height], resample=method)
		image = np.asarray(image)
	else:
		image = Image.fromarray(image.reshape(height, width))
		image = image.resize([new_width, new_height], resample=method)
		image = np.asarray(image)
		image = image.reshape(new_height, new_width, 1)
	return image


def load_image(filename, width=0, height=0, channels=0, alignment=0, print_console=True):
	if not os.path.isfile(filename):
		raise LoadError("File not found [%s]" % filename)
	image = misc.imread(filename)

	if len(image.shape) == 2:
		image = image.reshape(image.shape[0], image.shape[1], 1)
	if (width != 0 and image.shape[1] != width) or (height != 0 and image.shape[0] != height):
		raise LoadError("Attributes mismatch")
	if channels != 0 and image.shape[2] != channels:
		raise LoadError("Attributes mismatch")
	if alignment != 0 and ((width % alignment) != 0 or (height % alignment) != 0):
		raise LoadError("Attributes mismatch")

	if print_console:
		print("Loaded [%s]: %d x %d x %d" % (filename, image.shape[1], image.shape[0], image.shape[2]))
	return image


def load_image_data(filename, width=0, height=0, channels=0, alignment=0, print_console=True):
	if not os.path.isfile(filename):
		raise LoadError("File not found")
	image = np.load(filename)

	if (width != 0 and image.shape[1] != width) or (height != 0 and image.shape[0] != height):
		raise LoadError("Attributes mismatch")
	if channels != 0 and image.shape[2] != channels:
		raise LoadError("Attributes mismatch")
	if alignment != 0 and ((width % alignment) != 0 or (height % alignment) != 0):
		raise LoadError("Attributes mismatch")

	if print_console:
		print("Loaded [%s]: %d x %d x %d" % (filename, image.shape[1], image.shape[0], image.shape[2]))
	return image


def get_split_images(image, window_size, stride=None, enable_duplicate=False):
	if len(image.shape) == 3 and image.shape[2] == 1:
		image = image.reshape(image.shape[0], image.shape[1])

	window_size = int(window_size)
	size = image.itemsize  # byte size of each value
	height, width = image.shape
	if stride is None:
		stride = window_size
	else:
		stride = int(stride)

	if height < window_size or width < window_size:
		return None

	new_height = 1 + (height - window_size) // stride
	new_width = 1 + (width - window_size) // stride

	shape = (new_height, new_width, window_size, window_size)
	strides = size * np.array([width * stride, stride, width, 1])
	windows = np.lib.stride_tricks.as_strided(image, shape=shape, strides=strides)
	windows = windows.reshape(windows.shape[0] * windows.shape[1], windows.shape[2], windows.shape[3], 1)

	if enable_duplicate:
		extra_windows = []
		if (height - window_size) % stride != 0:
			for x in range(0, width - window_size, stride):
				extra_windows.append(image[height - window_size - 1:height - 1, x:x + window_size:])

		if (width - window_size) % stride != 0:
			for y in range(0, height - window_size, stride):
				extra_windows.append(image[y: y + window_size, width - window_size - 1:width - 1])

		if len(extra_windows) > 0:
			org_size = windows.shape[0]
			windows = np.resize(windows,
			                    [org_size + len(extra_windows), windows.shape[1], windows.shape[2], windows.shape[3]])
			for i in range(len(extra_windows)):
				extra_windows[i] = extra_windows[i].reshape([extra_windows[i].shape[0], extra_windows[i].shape[1], 1])
				windows[org_size + i] = extra_windows[i]

	return windows


# divide images with given stride. will return variable size images. not allowed to be overlapped or less except frame.
def get_divided_images(image, window_size, stride, min_size=0):

	h, w = image.shape[:2]
	divided_images = []

	for y in range(0, h, stride):
		for x in range(0, w, stride):

			new_h = window_size if y+window_size <= h else h - y
			new_w = window_size if x+window_size <= w else w - x
			if new_h < min_size or new_w < min_size:
				continue

#			print ("(%d,%d-%d,%d)"%(x,y, x+new_w, y+new_h))
			divided_images.append( image[y:y + new_h, x:x + new_w, :] )

	return divided_images


def xavier_cnn_initializer(shape, uniform=True):
	fan_in = shape[0] * shape[1] * shape[2]
	fan_out = shape[0] * shape[1] * shape[3]
	n = fan_in + fan_out
	if uniform:
		init_range = math.sqrt(6.0 / n)
		return tf.random_uniform(shape, minval=-init_range, maxval=init_range)
	else:
		stddev = math.sqrt(3.0 / n)
		return tf.truncated_normal(shape=shape, stddev=stddev)


def he_initializer(shape):
	n = shape[0] * shape[1] * shape[2]
	stddev = math.sqrt(2.0 / n)
	return tf.truncated_normal(shape=shape, stddev=stddev)

def upsample_filter(size):

	factor = (size + 1) // 2
	if size % 2 == 1:
		center = factor - 1
	else:
		center = factor - 0.5
	og = np.ogrid[:size, :size]

	return (1 - abs(og[0] - center) / factor) * (1 - abs(og[1] - center) / factor)

def get_upscale_filter_size(scale):
	return 2 * scale - scale % 2

def upscale_weight(scale, channels, name="weight"):

	cnn_size = get_upscale_filter_size(scale)

	initial = np.zeros(shape=[cnn_size, cnn_size, channels, channels],dtype=np.float32)
	filter=upsample_filter(cnn_size)

	for i in range(channels):
		initial[:, :, i, i] = filter

	return tf.Variable(initial, name=name)


def weight(shape, stddev=0.01, name="weight", uniform=False, initializer="stddev"):
	if initializer == "xavier":
		initial = xavier_cnn_initializer(shape, uniform=uniform)
	elif initializer == "he":
		initial = he_initializer(shape)
	elif initializer == "uniform":
		initial = tf.random_uniform(shape, minval=-2.0 * stddev, maxval=2.0 * stddev)
	elif initializer == "stddev":
		initial = tf.truncated_normal(shape=shape, stddev=stddev)
	elif initializer == "identity":
		initial = he_initializer(shape)
		if len(shape) == 4:
			initial = initial.eval()
			i = shape[0] // 2
			j = shape[1] // 2
			for k in range(min(shape[2], shape[3])):
				initial[i][j][k][k] = 1.0
	else:
		initial = tf.zeros(shape)

	return tf.Variable(initial, name=name)


def bias(shape, initial_value=0.0, name=None):
	initial = tf.constant(initial_value, shape=shape)

	if name is None:
		return tf.Variable(initial)
	else:
		return tf.Variable(initial, name=name)


# utilities for logging -----

def add_summaries(scope_name, model_name, var, save_stddev=True, save_mean=False, save_max=False, save_min=False):
	with tf.name_scope(scope_name):
		mean_var = tf.reduce_mean(var)
		if save_mean:
			tf.summary.scalar("mean/" + model_name, mean_var)

		if save_stddev:
			stddev_var = tf.sqrt(tf.reduce_mean(tf.square(var - mean_var)))
			tf.summary.scalar("stddev/" + model_name, stddev_var)

		if save_max:
			tf.summary.scalar("max/" + model_name, tf.reduce_max(var))

		if save_min:
			tf.summary.scalar("min/" + model_name, tf.reduce_min(var))
		tf.summary.histogram(model_name, var)

def log_scalar_value(writer, name, value, step):

	summary = tf.Summary(value=[tf.Summary.Value(tag=name, simple_value=value)])
	writer.add_summary(summary, step)


def get_now_date():
	d = datetime.datetime.today()
	return "%s/%s/%s %s:%s:%s" % (d.year, d.month, d.day, d.hour, d.minute, d.second)


def get_loss_image(image1, image2, scale=1.0, border_size=0):
	if len(image1.shape) == 2:
		image1 = image1.reshape(image1.shape[0], image1.shape[1], 1)
	if len(image2.shape) == 2:
		image2 = image2.reshape(image2.shape[0], image2.shape[1], 1)

	if image1.shape[0] != image2.shape[0] or image1.shape[1] != image2.shape[1] or image1.shape[2] != image2.shape[2]:
		return None

	if image1.dtype == np.uint8:
		image1 = image1.astype(np.double)
	if image2.dtype == np.uint8:
		image2 = image2.astype(np.double)

	loss_image = np.multiply(np.square(np.subtract(image1, image2)), scale)
	loss_image = np.minimum(loss_image, 255.0)
	loss_image = loss_image[border_size:-border_size, border_size:-border_size, :]

	return loss_image


def compute_mse(image1, image2, border_size=0):
	if len(image1.shape) == 2:
		image1 = image1.reshape(image1.shape[0], image1.shape[1], 1)
	if len(image2.shape) == 2:
		image2 = image2.reshape(image2.shape[0], image2.shape[1], 1)

	if image1.shape[0] != image2.shape[0] or image1.shape[1] != image2.shape[1] or image1.shape[2] != image2.shape[2]:
		return None

	image1 = np.clip(image1, 0, 255)
	image2 = np.clip(image2, 0, 255)
	if image1.dtype != np.uint8:
		image1 = image1.astype(np.uint8)
	image1 = image1.astype(np.double)
	if image2.dtype != np.uint8:
		image2 = image2.astype(np.uint8)
	image2 = image2.astype(np.double)

	mse = 0.0
	for i in range(border_size, image1.shape[0] - border_size):
		for j in range(border_size, image1.shape[1] - border_size):
			for k in range(image1.shape[2]):
				error = image1[i, j, k] - image2[i, j, k]
				mse += error * error

	return mse / ((image1.shape[0] - 2 * border_size) * (image1.shape[1] - 2 * border_size) * image1.shape[2])


def print_filter_weights(tensor):
	print("Tensor[%s] shape=%s" % (tensor.name, str(tensor.get_shape())))
	weight = tensor.eval()
	for i in range(weight.shape[3]):
		values = ""
		for x in range(weight.shape[0]):
			for y in range(weight.shape[1]):
				for c in range(weight.shape[2]):
					values += "%2.3f " % weight[y][x][c][i]
		print(values)
	print("\n")


def print_filter_biases(tensor):
	print("Tensor[%s] shape=%s" % (tensor.name, str(tensor.get_shape())))
	bias = tensor.eval()
	values = ""
	for i in range(bias.shape[0]):
		values += "%2.3f " % bias[i]
	print(values + "\n")


def get_psnr(mse, max_value=255.0):
	if mse is None or mse == float('Inf') or mse == 0:
		psnr = 0
	else:
		psnr = 20 * math.log(max_value / math.sqrt(mse), 10)
	return psnr


def print_num_of_total_parameters(output_detail=False, output_to_logging=False):
	total_parameters = 0
	parameters_string = ""

	for variable in tf.trainable_variables():

		shape = variable.get_shape()
		variable_parameters = 1
		for dim in shape:
			variable_parameters *= dim.value
		total_parameters += variable_parameters
		if len(shape) == 1:
			parameters_string += ("%s %d, " % (variable.name, variable_parameters))
		else:
			parameters_string += ("%s %s=%d, " % (variable.name, str(shape), variable_parameters))

	if output_to_logging:
		if output_detail:
			logging.info(parameters_string)
		logging.info("Total %d variables, %s params" % (len(tf.trainable_variables()), "{:,}".format(total_parameters)))
	else:
		if output_detail:
			print(parameters_string)
		print("Total %d variables, %s params" % (len(tf.trainable_variables()), "{:,}".format(total_parameters)))

def plot_with_labels(attributes, filename, markers=None, perplexity=25, n_iter=1000):
	print('Drawing scatter plot on [%s]...' % filename)

	if attributes.shape[1] > 2:
		print('Reducing attributes...')
		tsne = TSNE(perplexity=perplexity, n_components=2, init='pca', n_iter=n_iter)
		attributes = tsne.fit_transform(attributes)

	plt.rcParams.update({'font.size': 20})
	plt.figure(figsize=(40, 40))  # in inches

	for i in range(0, len(attributes)):
		x, y = attributes[i, :]

		if markers is None:
			plot_scatter(x, y)
		else:
			plot_scatter(x, y, marker=markers[i])

	for i in range(8):
		plt.scatter(-1000 + (i+1)*40, 110, color=MARKERS[i][0], s=MARKERS[i][1] * 9 // 2, marker=MARKERS[i][2])

	plt.savefig(filename)

def plot_scatter(x, y, marker=0):
	if marker >= len(MARKERS):
		marker = len(MARKERS) - 1

	plt.scatter(x, y, color=MARKERS[marker][0], s=MARKERS[marker][1] * 3 // 2, marker=MARKERS[marker][2])


def flip(image, type, invert=False):
	if type == 0:
		return image
	elif type == 1:
		return np.flipud(image)
	elif type == 2:
		return np.fliplr(image)
	elif type == 3:
		return np.flipud(np.fliplr(image))
	elif type == 4:
		return np.rot90(image, 1 if invert is False else -1)
	elif type == 5:
		return np.rot90(image, -1 if invert is False else 1)
	elif type == 6:
		if invert is False:
			return np.flipud(np.rot90(image))
		else:
			return np.rot90(np.flipud(image), -1)
	elif type == 7:
		if invert is False:
			return np.flipud(np.rot90(image, -1))
		else:
			return np.rot90(np.flipud(image), 1)


def get_from_ini(filename, section, key, default, create_if_empty=True):
	config = configparser.ConfigParser()
	try:
		with open(filename) as f:
			config.read_file(f)
		return config.get(section, key)

	except (IOError, configparser.NoOptionError):

		if create_if_empty:
			config = configparser.ConfigParser()
			config.add_section(section)
			config.set(section, key, str(default))

		with open(filename, "w") as configfile:
			config.write(configfile)

	return default


def scale(data, input_min, input_max, output_min, output_max):
	if (output_min == input_min and output_max == input_max):
		return data

	scale = (output_max - output_min) / (input_max - input_min)
	minimum = - scale * input_min + output_min

	if data.dtype == np.uint8:
		data = data.astype(np.double)

	data = np.multiply(data, scale)
	#	data *= scale """ This is faster but also original data will be scaled """
	data += minimum
	return data
