import argparse
import numpy as np
import os

# os.environ["CUDA_VISIBLE_DEVICES"]="1"

from keras import optimizers
from keras.callbacks import ModelCheckpoint, TensorBoard, CSVLogger
from keras.losses import categorical_crossentropy

from DataGenerator import DataGenerator
from ModelUtils import create_model_class, parse_epoch

SNAPSHOTS_PATH = "snapshots"
IMAGE_WIDTH = 224
IMAGE_HEIGHT = 224
BATCH_SIZE = 16
SEGMENTATION = True

np.random.seed(1337)  # for reproducibility


def finetune(args):
    train_data_generator = DataGenerator(args.data_root, "train", 90, (0.7, 1.2), (1, 3), 0.3, 0.3, 5, BATCH_SIZE,
                                         (IMAGE_HEIGHT, IMAGE_WIDTH), args.debug_epochs, True, True, True, SEGMENTATION)
    val_data_generator = DataGenerator(args.data_root, "val", 90, (0.7, 1.2), (1, 3), 0.3, 0.3, 5, BATCH_SIZE,
                                         (IMAGE_HEIGHT, IMAGE_WIDTH), 0, True, True, True, SEGMENTATION)

    num_classes = train_data_generator.get_num_classes()

    # creating model
    model_name = args.model
    model_obj = create_model_class(model_name)
    model = model_obj.create_model(IMAGE_WIDTH, IMAGE_HEIGHT, num_classes)

    # preparing directories for snapshots
    if not os.path.exists(SNAPSHOTS_PATH):
        os.mkdir(SNAPSHOTS_PATH)

    model_snapshot_path = os.path.join(SNAPSHOTS_PATH, model_name)
    if not os.path.exists(model_snapshot_path):
        os.mkdir(model_snapshot_path)

    # saving labels to ints mapping
    train_data_generator.dump_labels_to_int_mapping(os.path.join(model_snapshot_path, "labels.csv"))

    start_epoch = 0
    if args.snapshot is not None:
        start_epoch = parse_epoch(args.snapshot)
        print("loading weights from epoch %d" % start_epoch)
        model.load_weights(os.path.join(model_snapshot_path, args.snapshot), by_name=True)

    # print summary
    model.summary()

    nb_epoch = 800
    sgd = optimizers.Adam(lr=1e-5, decay=1e-4, beta_1=0.9)

    # selecting loss functions and weights
    losses = {}
    loss_weights = {}
    metrics = {}
    if SEGMENTATION:
        # segmentation and classification mode
        losses['segm_out'] = categorical_crossentropy
        loss_weights['segm_out'] = 1.0
        metrics['segm_out'] = 'accuracy'
        losses['class_out'] = categorical_crossentropy
        loss_weights['class_out'] = 1.0
        metrics['class_out'] = 'accuracy'
    else:
        # plain classification mode
        losses = 'categorical_crossentropy'
        loss_weights = None
        metrics = ['accuracy']

    model.compile(loss=losses, optimizer=sgd, metrics=metrics, loss_weights=loss_weights)
    filepath = os.path.join(model_snapshot_path, "weights-{epoch:03d}-{class_out_acc:.3f}.hdf5")
    checkpoint = ModelCheckpoint(filepath, monitor='class_out_acc', verbose=1, save_best_only=True, mode='max')

    logpath = "model_" + model_name + "_log.txt"
    csv_logger = CSVLogger(logpath)

    # log dir for tensorboard
    tb_log_dir = "model_" + model_name + "_tb"
    if os.path.exists(tb_log_dir):
        # clear_dir(tb_log_dir)
        pass
    else:
        os.mkdir(tb_log_dir)

    tb_log = TensorBoard(tb_log_dir)

    callbacks_list = [checkpoint, csv_logger, tb_log]

    model.fit_generator(generator=train_data_generator.generate(), steps_per_epoch=train_data_generator.get_steps_per_epoch(),
                        epochs=nb_epoch, callbacks=callbacks_list,
                        validation_data=val_data_generator.generate(), validation_steps=val_data_generator.get_steps_per_epoch(),
                        initial_epoch=start_epoch)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Finetune model')
    parser.add_argument("data_root", type=str, help="data root dir")
    parser.add_argument("--model", type=str, help="name of the model")
    parser.add_argument("--snapshot", type=str, help="restart from snapshot")
    parser.add_argument("--debug_epochs", type=int, default=0, help="number of epochs to save debug images")

    _args = parser.parse_args()
    finetune(_args)