import os
import pickle
import numpy as np
import tensorflow as tf
from PIL import Image


import keras
from keras import layers
from keras import models

from tqdm import tqdm
from scipy.io import wavfile
from multiprocessing import Process, Pool
import matplotlib.pyplot as plt
from pycochleagram import cochleagram as cgram

# Performance optimization
from timeit import default_timer as timer

def load_data(label='bird'):
	data_path ='../commands/train/audio/'
	labels = os.listdir(data_path)
	labels.remove('_background_noise_') # Remove background noise for now
	all_samples = {}
	for label in labels:
		all_samples[label] = {}
		for file in os.listdir(os.path.join(data_path, label)):
			name = file[:-4] # Remove .wav extension
			samplerate, data = wavfile.read(os.path.join(data_path, label, file))
			if len(data) < 16000:
				data = np.append(data, [0]*(16000-len(data)))
			all_samples[label][name] = data

	return all_samples, labels

def resample(example, new_size):
    im = Image.fromarray(example)
    resized_image = im.resize(new_size, resample=Image.ANTIALIAS)
    return np.array(resized_image)

def plot_cochleagram(cochleagram, title):
    plt.figure(figsize=(6,3))
    plt.matshow(cochleagram.reshape(256,256), origin='lower',cmap=plt.cm.Blues, fignum=False, aspect='auto')
    plt.yticks([])
    plt.xticks([])
    plt.title(title)
    plt.show()


def generate_cochleagram(wav_f, sr, title):
	# define parameters
	#wav_f, name, label, sr, return_dict = all_args
	n, sampling_rate = 50, 16000
	low_lim, hi_lim = 20, 8000
	sample_factor, pad_factor, downsample = 4, 2, 400
	nonlinearity, fft_mode, ret_mode = 'power', 'auto', 'envs'
	strict = True
	# create cochleagram
	c_gram = cgram.cochleagram(wav_f, sr, n, low_lim, hi_lim,
							   sample_factor, pad_factor, downsample,
							   nonlinearity, fft_mode, ret_mode, strict)

	# rescale to [0,255]
	c_gram_rescaled =  255*(1-((np.max(c_gram)-c_gram)/np.ptp(c_gram)))

	# reshape to (256,256)
	c_gram_reshape_1 = np.reshape(c_gram_rescaled, (211,400))
	c_gram_reshape_2 = resample(c_gram_reshape_1,(256,256))


	#plot_cochleagram(c_gram_reshape_2, title)

	# prepare to run through netwmap cork -- i.e., flatten it
	c_gram_flatten = np.reshape(c_gram_reshape_2, (1, 256*256))

	#return_dict[label][title] = c_gram_flatten

	return c_gram_flatten


def define_model():
	rnorm_bias, rnorm_alpha, rnorm_beta = 1., 1e-3, 0.75

	def Conv(params):
		return layers.Conv2D(params['filters'], params['kernel_size'],
							 params['strides'], padding='SAME', activation='relu')

	def Pooling(params):
		return layers.MaxPooling2D(params['pool_size'], params['strides'], padding='SAME')

	def Norm(params):
		return layers.Lambda(tf.nn.local_response_normalization(depth_radius = params['radius'],
												  bias = rnorm_bias,
												  alpha = rnorm_alpha,
												  beta = rnorm_beta ))
	def Dense(params):
		return layers.Dense(params['n_neurons'])

	common = {
	'conv_1': {'filters': 96, 'kernel_size': [9, 9], 'strides': [3, 3]},
	'conv_2': {'filters': 256, 'kernel_size': [5, 5], 'strides': [2, 2]},
	'conv_3': {'filters': 512, 'kernel_size': [3, 3], 'strides': [1, 1]},

	'pool_1': {'pool_size': [3, 3], 'strides': [2, 2]},
	'pool_2': {'pool_size': [3, 3], 'strides': [2, 2]},

	'norm_1': {'radius': 2, 'bias': 1, 'alpha': 1e-3, 'beta': 0.75},
	'norm_2': {'radius': 2, 'bias': 1, 'alpha': 1e-3, 'beta': 0.75}
	}

	speech = {
	'conv_4': {'filters': 96, 'kernel_size': [9, 9], 'strides': [3, 3]},
	'conv_5': {'filters': 256, 'kernel_size': [5, 5], 'strides': [2, 2]},

	'pool_3': {'pool_size': [3, 3], 'strides': [2, 2]}, # average pool, careful

	'dense_1': {'n_neurons': 64}

	}

	model = keras.Sequential()

	model.add(Conv(common['conv_1']))
	#model.add(Norm(common['norm_1']))
	model.add(Pooling(common['pool_1']))

	model.add(Conv(common['conv_2']))
	#model.add(Norm(common['norm_2']))
	model.add(Pooling(common['pool_2']))

	model.add(Conv(common['conv_3']))

	# Speech Branch
	model.add(Conv(speech['conv_4']))
	model.add(Conv(speech['conv_5']))
	model.add(Dense(speech['dense_1']))

	return model

all_samples, labels = load_data()
model = define_model()

all_coch = {}
for label in labels[:2]:
	all_coch[label] = {}
	for name in tqdm(all_samples[label]):
		current_file = all_samples[label][name]
		c_gram = generate_cochleagram(current_file, 16000, name)
		all_coch[label][name] = c_gram


# files = [all_samples[label][file] for label in labels for file in all_samples[label]]
# names = [file for label in labels for file in all_samples[label]]
# labels = [label for label in labels for file in all_samples[label]]
# procs = []

# all_coch = {}
# for label in labels:
# 	all_coch[label] = {}

# all_args = [(file, name, label, 16000, all_coch) for file, name, label in zip(files, names, labels)]
# print(len(all_args))


# for i, (file, name, label) in enumerate(zip(files, names, labels))
# 	proc = Process(target=generate_cochleagram, args=(file, 16000, name, label, all_coch))
# 	procs.append(proc)
# 	proc.start()

# for proc in procs:
# 	proc.join()

# def log_result(retval):
#     print('Done')

# pool = Pool(processes=4)
# pool.map_async(generate_cochleagram, all_args, callback=log_result)
# pool.close()
# pool.join()

if not os.path.exists('../Output/Cochleograms/'):
	os.makedirs('../Output/Cochleograms/')

pickle.dump(all_coch, open('../Output/Cochleograms/all_coch.pkl', 'wb'))